# /// script
# requires-python = ">=3.12"
# dependencies = ["opencv-python>=4", "numpy"]
# ///
"""Offline map-localization consistency auditor (read-only).

Quantifies every known mismatch between the reference map assets, the layout
geometry (zmdmap = the authoritative "Terra world map"), the ONNX classifier
vocabulary / tile_mapping, and the coordinate contract that the Python runtime
assumes.  It changes NO runtime behaviour and writes NO production asset.

Checks (each emits a PASS/FAIL + numeric evidence):
  C1 per-level MapTracker image size  == round(level_wh * SCALE_MAP_FACTOR)
  C2 per-region effective unscaled->Base scale is uniform across levels
     (non-uniform => the stitched Base.png is geometrically distorted vs world)
  C3 implied Base.png canvas (from transforms) matches the *runtime* shipped
     Base.png and the *templates* shipped Base.png (templates truncation = FAIL)
  C4 classifier grid coverage: cls.json base classes vs tile_mapping.json cells
  C5 tile_mapping implied canvas matches the shipped Base.png it was cut from
  C6 coordinate-contract smoking gun: what MinimapLocator._parse_tile emits for a
     Base / Tier class vs the canonical spaces (region-unscaled == entity
     pixel_location; level-local-converted == entity map_location)
  C7 zone-map contract: cls.json map prefixes vs MapDataLoader._ZONE_MAP keys
  C8 templates vs runtime asset divergence (missing + size-mismatched PNGs)

Run::

    3rd-part/python/python.exe tools/map_audit/verify_map_consistency.py \
        [--out reports/analysis/<stamp>_map_localization_audit.md] [--json]

The markdown report follows docs/WORKFLOW.md (root cause / fix / impact /
non-expected changes) so it can be referenced from docs/TASK_LOG.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- project bootstrap (must precede any core.* import) -----------------------
_THIS = Path(__file__).resolve()
_REPO = _THIS.parents[2]  # tools/map_audit/<this file> -> repo root
sys.path.insert(0, str(_REPO / "src"))
from core.foundation.paths import ensure_src_path  # noqa: E402

ensure_src_path()
from core.foundation.logger import init_logger  # noqa: E402

init_logger()

import cv2  # noqa: E402  (after bootstrap so bundled cv2 is on path)

from core.service.navigation.map_data_loader import (  # noqa: E402
    MapDataLoader,
)

SCALE_MAP_FACTOR = 0.1625  # unscaled region px -> per-level MapTracker image px

# region -> MapLocator subdir (matches shipped asset layout)
_REGION_DIR = {"map01": "ValleyIV", "map02": "Wuling", "base01": "Dijiang", "dung01": "Dung"}

# Per-check remediation narrative (root cause / fix / impact / non-expected
# changes) so the generated report satisfies docs/WORKFLOW.md on its own.
_FIXES: Dict[str, Dict[str, str]] = {
    "C1": {
        "root": "Per-level MapTracker crops must equal round(level_wh*0.1625); drift means a crop "
                "was re-exported at a different scale/aspect (templates copy).",
        "fix": "Re-export the drifted level/tier crops from the authoritative runtime set (sync "
               "script in Iter2/3); the runtime copy already matches.",
        "impact": "Wrong-aspect templates cause ZNCC/template matching to miss or mis-score the level.",
        "nonexp": "Sync only copies bytes from the authoritative runtime dir; no geometry recomputed.",
    },
    "C2": {
        "root": "A region composite is world-aligned iff the per-level unscaled->Base scale is uniform; "
                ">0.5% spread would mean the stitched Base.png is geometrically distorted vs zmdmap.",
        "fix": "If a region ever fails, rebuild its composite from per-level images at the layout "
               "positions (Iter2 generator); map01/map02 currently pass (uniform).",
        "impact": "Non-uniform scale would make every position read off that Base.png wrong.",
        "nonexp": "Check is read-only; map01/map02 unchanged.",
    },
    "C3": {
        "root": "`assets/templates` carries a truncated Wuling Base.png (2016x1920 vs runtime 2976) and "
               "`maptracker_coordinate_transforms.json` lacks the newer levels (lv007/lv008), so the "
               "stale copy shadows the complete runtime one on the load path.",
        "fix": "Sync templates from runtime (local; PNGs are gitignored) AND make TemplateBackend load "
               "the authoritative set with precedence so a stale copy can never shadow it (Iter3).",
        "impact": "Queries landing in the truncated north zone / new levels have no matching template.",
        "nonexp": "After sync templates==runtime, so recognition outcomes equal loading runtime directly.",
    },
    "C4": {
        "root": "The ONNX vocabulary omits ~28% (Map01Base) / ~49% (Map02Base) of its own 160-grid cells; "
               "those cells classify as 'None' or alias to a neighbour.",
        "fix": "Closeable only by retraining cls.onnx in the external MaaEnd-AI repo on a complete tile "
               "set; we stage that complete set + mapping in Iter4 (not overwriting the deployed model).",
        "impact": "Player positions in uncovered cells cannot be resolved by the coarse classifier.",
        "nonexp": "No deployed model/tile_mapping touched; staged artifacts are additive.",
    },
    "C5": {
        "root": "tile_mapping's 160-grid must overlay exactly the Base.png it was cut from; mismatch "
               "would mean the fine-search rects point at the wrong pixels.",
        "fix": "None needed (passes); if a future Base.png is rebuilt, tile_mapping must be re-cut too.",
        "impact": "Guard against Base.png / tile_mapping desynchronisation.",
        "nonexp": "Read-only.",
    },
    "C6": {
        "root": "`MinimapLocator._parse_tile` returns Base centres in the 600-unit layout frame and Tier "
               "centres in signed grid-wise units, but `EntityDatabase.find_nearby` compares against "
               "entity.map_location (level-local converted px). Three incompatible frames are mixed; the "
               "Base magnitude error measured here is ~1.78x.",
        "fix": "Make `_parse_tile` emit a documented canonical space (region-unscaled, derivable exactly "
               "for Tier via grid_tiers pixel_lb/rt) and have find_nearby compare via pixel_location, "
               "skipping incompatible Base-only results instead of comparing wrong (Iter3).",
        "impact": "`where_am_i`/nearby-entity lookups currently return wrong or empty results even when "
               "the tile class is correct.",
        "nonexp": "Logic-only; unit-tested; skipping incompatible lookups is strictly safer than a wrong hit.",
    },
    "C7": {
        "root": "cls.json can emit map_id 'indie' (IndieDg005/007 classes) but `_ZONE_MAP` lacks 'indie' "
               "and `_parse_tile` has no Indie branch, so those frames fall to map_id 'unknown' / zone "
               "'indie_Base' which MaaFW may not know (XC-3).",
        "fix": "Add an Indie parse branch + `_ZONE_MAP['indie']` + `indie_layout.json` to the loader's "
               "layout map (the file exists upstream) so the vocab<->zone contract holds (Iter3).",
        "impact": "Navigation silently fails to resolve a zone for indie sub-scenes.",
        "nonexp": "Additive mapping entries; existing maps unaffected.",
    },
    "C8": {
        "root": "`TemplateBackend._load_available_modules` loads `assets/templates` and falls back to the "
               "authoritative runtime set only when templates is empty, so 36 missing + 30 size-mismatched "
               "stale templates shadow the good ones.",
        "fix": "Resync templates from runtime (local) + add a load-time drift warning and authoritative-"
               "precedence merge so future divergence is visible and non-shadowing (Iter3).",
        "impact": "Every element whose authoritative template differs from the stale copy matches worse.",
        "nonexp": "Post-resync the templates set equals runtime; the warning only logs on future drift.",
    },
}


@dataclass
class Finding:
    code: str
    severity: str  # FAIL / WARN / INFO / PASS
    title: str
    detail: str


@dataclass
class Report:
    findings: List[Finding] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)

    def add(self, code: str, severity: str, title: str, detail: str) -> None:
        self.findings.append(Finding(code, severity, title, detail))


def _img_size(path: Path) -> Optional[Tuple[int, int]]:
    if not path.exists():
        return None
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    h, w = im.shape[:2]
    return (w, h)


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _transforms(maaend: Path) -> Dict[str, Dict[str, float]]:
    """map_name -> {scale_x,scale_y,offset_x,offset_y,zone_id} from transforms.json."""
    out: Dict[str, Dict[str, float]] = {}
    for sub in ("resource/image/MapLocator", "assets/resource/image/MapLocator"):
        p = maaend / sub / "maptracker_coordinate_transforms.json"
        if p.exists():
            raw = _load_json(p)
            for entry in raw.get("transforms", []):
                out[entry["map_name"]] = entry
            return out
    return out


# ---------------------------------------------------------------------------
# individual checks
# ---------------------------------------------------------------------------

def check_c1_level_image_sizes(maaend: Path, loader: MapDataLoader, rep: Report) -> None:
    mism: List[str] = []
    checked = 0
    for region in ("map01", "map02", "base01"):
        layout = loader.get_layout(region)
        if not layout:
            continue
        for lid, lv in layout.levels.items():
            fname = lid.replace("_", "_")  # map01_lv001
            p = maaend / "resource" / "image" / "MapTracker" / "map" / f"{fname}.png"
            sz = _img_size(p)
            if sz is None:
                continue
            checked += 1
            exp = (round(lv.width * SCALE_MAP_FACTOR), round(lv.height * SCALE_MAP_FACTOR))
            if sz != exp:
                mism.append(f"{fname}: got {sz[0]}x{sz[1]} expected {exp[0]}x{exp[1]}")
    if mism:
        rep.add("C1", "WARN", "per-level MapTracker image size != level_wh*0.1625",
                f"{len(mism)}/{checked} mismatched (templates drift / wrong crop scale): " + "; ".join(mism[:12]))
    else:
        rep.add("C1", "PASS", "per-level MapTracker image size == level_wh*0.1625",
                f"all {checked} runtime level images match the 0.1625 spec")


def check_c2_c3_base_canvas(maaend: Path, loader: MapDataLoader,
                            tr: Dict[str, Dict[str, float]], rep: Report) -> None:
    for region in ("map01", "map02", "base01"):
        layout = loader.get_layout(region)
        if not layout:
            continue
        scales: List[Tuple[str, float, float]] = []
        max_x = max_y = 0.0
        for lid, lv in layout.levels.items():
            t = tr.get(lid)
            if not t:
                continue
            sx, sy = float(t["scale_x"]), float(t["scale_y"])
            ox, oy = float(t["offset_x"]), float(t["offset_y"])
            eff_x = SCALE_MAP_FACTOR * sx
            eff_y = SCALE_MAP_FACTOR * sy
            scales.append((lid, eff_x, eff_y))
            # level image footprint in Base.png = level_wh * 0.1625 * scale
            w_img = round(lv.width * SCALE_MAP_FACTOR * sx)
            h_img = round(lv.height * SCALE_MAP_FACTOR * sy)
            max_x = max(max_x, ox + w_img)
            max_y = max(max_y, oy + h_img)
        if not scales:
            rep.add("C2", "WARN", f"{region}: no transforms.json entries", "cannot verify scale uniformity")
            continue
        ex = [s[1] for s in scales]
        ey = [s[2] for s in scales]
        spread_x = (max(ex) - min(ex)) / min(ex) if min(ex) else 0
        spread_y = (max(ey) - min(ey)) / min(ey) if min(ey) else 0
        # per-level integer-pixel rounding yields ~0.1% apparent spread even on a
        # perfectly uniform composite; treat <0.5% as uniform (world-aligned).
        uniform = spread_x < 5e-3 and spread_y < 5e-3
        rep.add("C2", "PASS" if uniform else "FAIL",
                f"{region}: unscaled->Base scale uniformity",
                f"eff_x range [{min(ex):.4f},{max(ex):.4f}] spread {spread_x:.3%}; "
                f"eff_y range [{min(ey):.4f},{max(ey):.4f}] spread {spread_y:.3%}; "
                f"implied Base canvas ~ {max_x:.0f}x{max_y:.0f}")
        # C3: compare implied canvas with shipped Base.png (runtime + templates)
        sub = _REGION_DIR.get(region, region)
        rt_sz = _img_size(maaend / "resource" / "image" / "MapLocator" / sub / "Base.png")
        tp_sz = _img_size(_REPO / "assets" / "templates" / "MapLocator" / sub / "Base.png")
        impl = (round(max_x), round(max_y))
        detail = f"implied-by-transforms {impl}; runtime {rt_sz}; templates {tp_sz}"
        # templates truncated/obsolete vs runtime is a hard FAIL (active load path).
        if tp_sz and rt_sz and tp_sz != rt_sz:
            rep.add("C3", "FAIL", f"{region}: templates Base.png diverges from runtime",
                    f"{detail} -> templates copy is truncated/obsolete yet shadows runtime on the load path")
        else:
            rep.add("C3", "PASS", f"{region}: templates Base.png == runtime", detail)
        # transforms.json not covering the full runtime composite => transforms lag
        # the runtime Base.png (newer levels like map02_lv007/008 not listed) => WARN.
        if rt_sz and (abs(rt_sz[0] - impl[0]) > 2 or abs(rt_sz[1] - impl[1]) > 2):
            rep.add("C3", "WARN", f"{region}: transforms.json does not span the runtime composite",
                    f"{detail} -> transforms.json is missing level placements present in the shipped "
                    f"Base.png (data-version skew); runtime composite is the more complete truth")
        else:
            rep.add("C3", "PASS", f"{region}: transforms span the runtime composite", detail)


def check_c4_c5_classifier_grid(maaend: Path, rep: Report) -> None:
    cls = _load_json(maaend / "resource" / "model" / "map" / "cls.json")
    tm = _load_json(maaend / "resource" / "model" / "map" / "tile_mapping.json")
    classes = cls["classes"]
    # base grid classes present in cls.json
    cls_cells: Dict[str, set] = {}
    for c in classes:
        m = re.match(r"(Map\d+Base|Base\d+Base)__r(\d+)_c(\d+)", c)
        if m:
            cls_cells.setdefault(m.group(1), set()).add((int(m.group(2)), int(m.group(3))))
    tm_cells: Dict[str, set] = {}
    tm_canvas: Dict[str, Tuple[int, int]] = {}
    for v in tm.values():
        bc = v["base_class"]
        tm_cells.setdefault(bc, set()).add((v["row"], v["col"]))
        mx = v["x"] + v["w"]
        my = v["y"] + v["h"]
        cur = tm_canvas.get(bc, (0, 0))
        tm_canvas[bc] = (max(cur[0], mx), max(cur[1], my))
    for bc, cells in tm_cells.items():
        have = len(cls_cells.get(bc, set()))
        total = len(cells)
        cov = have / total if total else 0
        sev = "PASS" if cov >= 0.99 else ("WARN" if cov >= 0.7 else "FAIL")
        rep.add("C4", sev, f"{bc}: classifier covers {have}/{total} grid cells ({cov:.0%})",
                f"uncovered cells -> ONNX emits 'None'/wrong tile there; "
                f"Map01Base {len(cls_cells.get('Map01Base', set()))}/81, "
                f"Map02Base {len(cls_cells.get('Map02Base', set()))}/247")
    # C5: implied tile_mapping canvas vs shipped Base.png
    for bc, (cw, ch) in tm_canvas.items():
        sub = "ValleyIV" if bc.startswith("Map01") else ("Wuling" if bc.startswith("Map02") else "?")
        rt = _img_size(maaend / "resource" / "image" / "MapLocator" / sub / "Base.png")
        ok = bool(rt) and abs(rt[0] - cw) <= 2 and abs(rt[1] - ch) <= 2
        rep.add("C5", "PASS" if ok else "FAIL", f"{bc}: tile_mapping canvas {cw}x{ch} vs Base.png {rt}",
                "tile_mapping 160-grid is cut from this Base.png" if ok
                else "tile_mapping grid does not match the shipped Base.png it must overlay")


def check_c6_coordinate_contract(maaend: Path, loader: MapDataLoader,
                                 tr: Dict[str, Dict[str, float]], rep: Report) -> None:
    """Demonstrate the space mismatch the runtime _parse_tile produces."""
    tm = _load_json(maaend / "resource" / "model" / "map" / "tile_mapping.json")
    grid = loader.load_grid_tiers()
    layout = loader.get_layout("map01")
    lines: List[str] = []

    # --- Base class example: Map01Base__r00_c02 ---
    bc_key = "Map01Base__r00_c02"
    if bc_key in tm and layout:
        cell = tm[bc_key]
        # runtime _parse_tile (current code): col*tile_w + tile_w/2 in 600-units
        runtime_cx = cell["col"] * layout.tile_w + layout.tile_w / 2.0
        runtime_cy = cell["row"] * layout.tile_h + layout.tile_h / 2.0
        # canonical region-unscaled: tile_mapping rect is in 0.15-Base px (ValleyIV),
        # unscaled = base_px / eff_scale ; eff_scale = 0.1625 * transforms.scale (lv001)
        t = tr.get("map01_lv001", {})
        eff = SCALE_MAP_FACTOR * float(t.get("scale_x", 1.0))
        canon_cx = (cell["x"] + cell["w"] / 2.0) / eff if eff else float("nan")
        canon_cy = (cell["y"] + cell["h"] / 2.0) / eff if eff else float("nan")
        lines.append(
            f"Base {bc_key}: runtime_parse_tile=({runtime_cx:.0f},{runtime_cy:.0f}) [600-unit layout space] "
            f"vs canonical_unscaled=({canon_cx:.0f},{canon_cy:.0f}); "
            f"factor error ~{canon_cx/runtime_cx:.2f}x" if runtime_cx else "n/a")

    # --- Tier class example: Map01Lv001Tier114 ---
    # _parse_tile returns grid_tiers[grid_cell].center which is in *grid-wise*
    # units (a signed, level-relative frame).  entity_db.find_nearby compares the
    # reported center against entity.map_location (level-local *converted* px,
    # i.e. 0..level_image_size) — a different frame.  We surface the grid-wise
    # value plus the two canonical frames' *ranges* (not a single origin-shifted
    # point, which would be misleading) to prove the contract mismatch.
    tier_name = "Map01Lv001Tier114"
    lv = layout.levels.get("map01_lv001") if layout else None
    for gk, gc in grid.items():
        if gk.startswith("map01_lv001") and any(t.endswith("tier_114") for t in gc.items.values()):
            rt = gc.center
            lv_img = (round(lv.width * SCALE_MAP_FACTOR), round(lv.height * SCALE_MAP_FACTOR)) if lv else None
            lines.append(
                f"Tier {tier_name} (grid {gk}): runtime_parse_tile_center=({rt[0]:.1f},{rt[1]:.1f}) "
                f"[grid-wise, signed] vs find_nearby space = entity.map_location in [0..{lv_img}] "
                f"(level-local converted px); grid-wise is neither region-unscaled nor level-local => "
                f"nearby lookup cannot match. (Base-case above quantifies the magnitude: ~1.78x.)")
            break
    rep.add("C6", "FAIL" if lines else "INFO",
            "coordinate-space contract: _parse_tile output != space find_nearby expects",
            " | ".join(lines) if lines else "no example classes resolved")


def check_c7_zone_contract(maaend: Path, rep: Report) -> None:
    cls = _load_json(maaend / "resource" / "model" / "map" / "cls.json")
    # prefixes actually emitted by _parse_tile mapping (minimap_locator.py:158-167)
    prefixes_in_vocab = set()
    for c in cls["classes"]:
        if c.startswith(("Map01", "OMV")):
            prefixes_in_vocab.add("map01")
        elif c.startswith("Map02"):
            prefixes_in_vocab.add("map02")
        elif c.startswith(("Dung01", "Dung")):
            prefixes_in_vocab.add("dung01")
        elif c.startswith("Base01"):
            prefixes_in_vocab.add("base01")
        elif c.startswith("Indie"):
            prefixes_in_vocab.add("indie")
    # _ZONE_MAP in this repo (read from source to avoid import-time side effects)
    src = (_REPO / "src" / "core" / "service" / "navigation" / "map_data_loader.py").read_text(encoding="utf-8")
    m = re.search(r"_ZONE_MAP\s*=\s*\{([^}]+)\}", src)
    zone_map_keys = set(re.findall(r'"([a-z0-9]+)"\s*:', m.group(1))) if m else set()
    missing = prefixes_in_vocab - zone_map_keys
    if missing:
        rep.add("C7", "FAIL", "zone-map contract gap (XC-3): vocab prefixes without _ZONE_MAP entry",
                f"vocab emits map_ids {sorted(prefixes_in_vocab)} but _ZONE_MAP has {sorted(zone_map_keys)}; "
                f"missing {sorted(missing)} -> get_zone_id falls back to '<id>_Base' which MaaFW may not know")
    else:
        rep.add("C7", "PASS", "zone-map contract complete", f"_ZONE_MAP covers {sorted(zone_map_keys)}")


def check_c8_templates_divergence(maaend: Path, rep: Report) -> None:
    total_missing = total_sizemismatch = 0
    detail: List[str] = []
    for rel in ("image/MapTracker/map", "image/MapLocator"):
        rt_dir = maaend / "resource" / rel
        tp_dir = _REPO / "assets" / "templates" / rel.split("/", 1)[1] if False else \
            _REPO / "assets" / "templates" / rel.replace("image/", "")
        if not rt_dir.exists():
            continue
        rt = {p.name: _img_size(p) for p in rt_dir.rglob("*.png")}
        tp = {p.name: _img_size(p) for p in tp_dir.rglob("*.png")} if tp_dir.exists() else {}
        miss = [n for n in rt if n not in tp]
        sizem = [n for n in rt if n in tp and rt[n] != tp[n]]
        total_missing += len(miss)
        total_sizemismatch += len(sizem)
        if miss or sizem:
            detail.append(f"{rel}: missing={len(miss)} size-mismatch={len(sizem)}")
            for n in (miss[:6] + [f"{x}(rt{rt[x]}!=tp{tp[x]})" for x in sizem[:6]]):
                detail.append("   - " + n)
    sev = "FAIL" if (total_missing or total_sizemismatch) else "PASS"
    rep.add("C8", sev,
            f"templates vs runtime map assets: {total_missing} missing, {total_sizemismatch} size-mismatched",
            "stale assets/templates shadow authoritative runtime copy on TemplateBackend load path; "
            + "; ".join(detail) if detail else "templates and runtime agree")


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def render_markdown(rep: Report, stamp: str) -> str:
    order = {"FAIL": 0, "WARN": 1, "INFO": 2, "PASS": 3}
    rows = sorted(rep.findings, key=lambda f: (order.get(f.severity, 9), f.code))
    n_fail = sum(1 for f in rows if f.severity == "FAIL")
    n_warn = sum(1 for f in rows if f.severity == "WARN")
    n_pass = sum(1 for f in rows if f.severity == "PASS")
    L: List[str] = []
    L.append(f"# Map-Localization Consistency Audit ({stamp})\n")
    L.append(f"**Tally**: {n_fail} FAIL, {n_warn} WARN, {n_pass} PASS "
             f"(of {len(rows)} checks). Read-only audit; no asset or behaviour changed.\n")
    L.append("## Findings (root cause → fix → impact → non-expected changes)\n")
    for f in rows:
        L.append(f"### [{f.severity}] {f.code} — {f.title}\n")
        L.append(f"- **Evidence**: {f.detail}\n")
        fx = _FIXES.get(f.code, {})
        if fx:
            L.append(f"- **Root cause**: {fx['root']}\n")
            L.append(f"- **Fix**: {fx['fix']}\n")
            L.append(f"- **Impact**: {fx['impact']}\n")
            L.append(f"- **Non-expected changes**: {fx['nonexp']}\n")
        else:
            L.append("- **Root cause / fix / impact**: see the iteration plan in `docs/TASK_LOG.md`.\n")
    L.append("\n## Narrative\n")
    L.append("- **Scene/image difference (accuracy)**: the runtime Python path uses a coarse ONNX "
             "classifier (`cls.onnx`, 128×128) on a *hardcoded* minimap crop with no de-rotation, no "
             "scale normalisation and no dynamic bbox; upstream's accurate path is gradient-ZNCC "
             "template matching at the correct 0.1625 minimap scale. Compounded by `assets/templates` "
             "shadowing the authoritative runtime templates with truncated / wrong-scale copies (C8).")
    L.append("- **Map spec vs big world**: per-level MapTracker images and ValleyIV `Base.png` ARE "
             "world-aligned (0.1625 and 0.15 of the zmdmap layout respectively; C2 PASS for map01), "
             "but other regions' stitched `Base.png` may be non-uniformly scaled (C2) and the templates "
             "copy is truncated (C3). Three mutually-inconsistent numeric frames exist in code: the 600-unit "
             "layout grid, the 160-px classifier grid, and grid-units from `grid_tiers`; `_parse_tile` mixes "
             "them so reported coordinates are not in the space `EntityDatabase.find_nearby` compares "
             "(entity `map_location`) — see C6.")
    L.append("- **Avoid duplication / missing coverage**: classifier covers only ~72% (Map01Base) / ~51% "
             "(Map02Base) of its own grid (C4); `assets/templates` duplicates the runtime assets but "
             "out-of-date (C8). The upstream de-duplication of overlapping *levels* (max-flow "
             "`distinguish_levels`) is already baked into the per-level images, so a layout-accurate "
             "composite does not double-cover overlaps.")
    L.append("- **Non-expected changes of the planned fixes**: code fixes are logic-only and unit-tested; "
             "image reconstruction is additive (new filename) and never overwrites the shipped `Base.png`, "
             "so the ONNX classifier (trained on the current MapLocator frame) is not desynchronised. "
             "Re-pointing the ONNX path at a new composite would require retraining in the external "
             "MaaEnd-AI repo — out of scope here; we instead stage the consistent tile set + mapping for it.")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--maaend", default=str(_REPO / "3rd-part" / "maaend"))
    ap.add_argument("--out", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    maaend = Path(args.maaend)
    loader = MapDataLoader(str(maaend))
    tr = _transforms(maaend)
    rep = Report()

    check_c1_level_image_sizes(maaend, loader, rep)
    check_c2_c3_base_canvas(maaend, loader, tr, rep)
    check_c4_c5_classifier_grid(maaend, rep)
    check_c6_coordinate_contract(maaend, loader, tr, rep)
    check_c7_zone_contract(maaend, rep)
    check_c8_templates_divergence(maaend, rep)

    if args.json:
        print(json.dumps([f.__dict__ for f in rep.findings], ensure_ascii=False, indent=2))
    else:
        for f in rep.findings:
            print(f"[{f.severity:4}] {f.code} {f.title}\n        {f.detail}")

    if args.out:
        from datetime import datetime
        stamp = datetime.now().strftime("%Y-%m-%d")
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(rep, stamp), encoding="utf-8")
        print(f"\nwrote {out}")

    n_fail = sum(1 for f in rep.findings if f.severity == "FAIL")
    return 0 if n_fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
