# Map-Localization Consistency Audit (2026-07-31)

**Tally**: 5 FAIL, 3 WARN, 7 PASS (of 15 checks). Read-only audit; no asset or behaviour changed.

## Findings (root cause → fix → impact → non-expected changes)

### [FAIL] C3 — map02: templates Base.png diverges from runtime

- **Evidence**: implied-by-transforms (1632, 2880); runtime (2016, 2976); templates (2016, 1920) -> templates copy is truncated/obsolete yet shadows runtime on the load path

- **Root cause**: `assets/templates` carries a truncated Wuling Base.png (2016x1920 vs runtime 2976) and `maptracker_coordinate_transforms.json` lacks the newer levels (lv007/lv008), so the stale copy shadows the complete runtime one on the load path.

- **Fix**: Sync templates from runtime (local; PNGs are gitignored) AND make TemplateBackend load the authoritative set with precedence so a stale copy can never shadow it (Iter3).

- **Impact**: Queries landing in the truncated north zone / new levels have no matching template.

- **Non-expected changes**: After sync templates==runtime, so recognition outcomes equal loading runtime directly.

### [FAIL] C4 — Map02Base: classifier covers 125/247 grid cells (51%)

- **Evidence**: uncovered cells -> ONNX emits 'None'/wrong tile there; Map01Base 58/81, Map02Base 125/247

- **Root cause**: The ONNX vocabulary omits ~28% (Map01Base) / ~49% (Map02Base) of its own 160-grid cells; those cells classify as 'None' or alias to a neighbour.

- **Fix**: Closeable only by retraining cls.onnx in the external MaaEnd-AI repo on a complete tile set; we stage that complete set + mapping in Iter4 (not overwriting the deployed model).

- **Impact**: Player positions in uncovered cells cannot be resolved by the coarse classifier.

- **Non-expected changes**: No deployed model/tile_mapping touched; staged artifacts are additive.

### [FAIL] C6 — coordinate-space contract: _parse_tile output != space find_nearby expects

- **Evidence**: Base Map01Base__r00_c02: runtime_parse_tile=(1500,300) [600-unit layout space] vs canonical_unscaled=(2667,533); factor error ~1.78x | Tier Map01Lv001Tier114 (grid map01_lv001_8_3): runtime_parse_tile_center=(64.0,-384.0) [grid-wise, signed] vs find_nearby space = entity.map_location in [0..(975, 780)] (level-local converted px); grid-wise is neither region-unscaled nor level-local => nearby lookup cannot match. (Base-case above quantifies the magnitude: ~1.78x.)

- **Root cause**: `MinimapLocator._parse_tile` returns Base centres in the 600-unit layout frame and Tier centres in signed grid-wise units, but `EntityDatabase.find_nearby` compares against entity.map_location (level-local converted px). Three incompatible frames are mixed; the Base magnitude error measured here is ~1.78x.

- **Fix**: Make `_parse_tile` emit a documented canonical space (region-unscaled, derivable exactly for Tier via grid_tiers pixel_lb/rt) and have find_nearby compare via pixel_location, skipping incompatible Base-only results instead of comparing wrong (Iter3).

- **Impact**: `where_am_i`/nearby-entity lookups currently return wrong or empty results even when the tile class is correct.

- **Non-expected changes**: Logic-only; unit-tested; skipping incompatible lookups is strictly safer than a wrong hit.

### [FAIL] C7 — zone-map contract gap (XC-3): vocab prefixes without _ZONE_MAP entry

- **Evidence**: vocab emits map_ids ['dung01', 'indie', 'map01', 'map02'] but _ZONE_MAP has ['base01', 'dung01', 'map01', 'map02']; missing ['indie'] -> get_zone_id falls back to '<id>_Base' which MaaFW may not know

- **Root cause**: cls.json can emit map_id 'indie' (IndieDg005/007 classes) but `_ZONE_MAP` lacks 'indie' and `_parse_tile` has no Indie branch, so those frames fall to map_id 'unknown' / zone 'indie_Base' which MaaFW may not know (XC-3).

- **Fix**: Add an Indie parse branch + `_ZONE_MAP['indie']` + `indie_layout.json` to the loader's layout map (the file exists upstream) so the vocab<->zone contract holds (Iter3).

- **Impact**: Navigation silently fails to resolve a zone for indie sub-scenes.

- **Non-expected changes**: Additive mapping entries; existing maps unaffected.

### [FAIL] C8 — templates vs runtime map assets: 36 missing, 30 size-mismatched

- **Evidence**: stale assets/templates shadow authoritative runtime copy on TemplateBackend load path; image/MapTracker/map: missing=15 size-mismatch=5;    - indie_dg007_tier_335.png;    - indie_dg007_tier_336.png;    - indie_dg007_tier_337.png;    - indie_dg007_tier_338.png;    - map02_lv007.png;    - map02_lv007_tier_392.png;    - map01_lv003.png(rt(488, 488)!=tp(488, 487));    - map01_lv003_tier_17.png(rt(488, 488)!=tp(488, 487));    - map01_lv003_tier_18.png(rt(488, 488)!=tp(488, 487));    - map01_lv003_tier_19.png(rt(488, 488)!=tp(488, 487));    - map01_lv003_tier_31.png(rt(488, 488)!=tp(488, 487)); image/MapLocator: missing=21 size-mismatch=25;    - Dung01Tier186.png;    - Dung01Tier62.png;    - Dung01Tier63.png;    - Dung01Tier66.png;    - IndieDg005Base.png;    - IndieDg007Base.png;    - Dung01Tier187.png(rt(256, 256)!=tp(504, 581));    - Dung01Tier52.png(rt(256, 352)!=tp(579, 678));    - Dung01Tier54.png(rt(256, 256)!=tp(579, 582));    - Dung01Tier56.png(rt(256, 256)!=tp(562, 592));    - Base.png(rt(2016, 2976)!=tp(2016, 1920));    - Lv001Tier173.png(rt(256, 256)!=tp(223, 256))

- **Root cause**: `TemplateBackend._load_available_modules` loads `assets/templates` and falls back to the authoritative runtime set only when templates is empty, so 36 missing + 30 size-mismatched stale templates shadow the good ones.

- **Fix**: Resync templates from runtime (local) + add a load-time drift warning and authoritative-precedence merge so future divergence is visible and non-shadowing (Iter3).

- **Impact**: Every element whose authoritative template differs from the stale copy matches worse.

- **Non-expected changes**: Post-resync the templates set equals runtime; the warning only logs on future drift.

### [WARN] C2 — base01: no transforms.json entries

- **Evidence**: cannot verify scale uniformity

- **Root cause**: A region composite is world-aligned iff the per-level unscaled->Base scale is uniform; >0.5% spread would mean the stitched Base.png is geometrically distorted vs zmdmap.

- **Fix**: If a region ever fails, rebuild its composite from per-level images at the layout positions (Iter2 generator); map01/map02 currently pass (uniform).

- **Impact**: Non-uniform scale would make every position read off that Base.png wrong.

- **Non-expected changes**: Check is read-only; map01/map02 unchanged.

### [WARN] C3 — map02: transforms.json does not span the runtime composite

- **Evidence**: implied-by-transforms (1632, 2880); runtime (2016, 2976); templates (2016, 1920) -> transforms.json is missing level placements present in the shipped Base.png (data-version skew); runtime composite is the more complete truth

- **Root cause**: `assets/templates` carries a truncated Wuling Base.png (2016x1920 vs runtime 2976) and `maptracker_coordinate_transforms.json` lacks the newer levels (lv007/lv008), so the stale copy shadows the complete runtime one on the load path.

- **Fix**: Sync templates from runtime (local; PNGs are gitignored) AND make TemplateBackend load the authoritative set with precedence so a stale copy can never shadow it (Iter3).

- **Impact**: Queries landing in the truncated north zone / new levels have no matching template.

- **Non-expected changes**: After sync templates==runtime, so recognition outcomes equal loading runtime directly.

### [WARN] C4 — Map01Base: classifier covers 58/81 grid cells (72%)

- **Evidence**: uncovered cells -> ONNX emits 'None'/wrong tile there; Map01Base 58/81, Map02Base 125/247

- **Root cause**: The ONNX vocabulary omits ~28% (Map01Base) / ~49% (Map02Base) of its own 160-grid cells; those cells classify as 'None' or alias to a neighbour.

- **Fix**: Closeable only by retraining cls.onnx in the external MaaEnd-AI repo on a complete tile set; we stage that complete set + mapping in Iter4 (not overwriting the deployed model).

- **Impact**: Player positions in uncovered cells cannot be resolved by the coarse classifier.

- **Non-expected changes**: No deployed model/tile_mapping touched; staged artifacts are additive.

### [PASS] C1 — per-level MapTracker image size == level_wh*0.1625

- **Evidence**: all 12 runtime level images match the 0.1625 spec

- **Root cause**: Per-level MapTracker crops must equal round(level_wh*0.1625); drift means a crop was re-exported at a different scale/aspect (templates copy).

- **Fix**: Re-export the drifted level/tier crops from the authoritative runtime set (sync script in Iter2/3); the runtime copy already matches.

- **Impact**: Wrong-aspect templates cause ZNCC/template matching to miss or mis-score the level.

- **Non-expected changes**: Sync only copies bytes from the authoritative runtime dir; no geometry recomputed.

### [PASS] C2 — map01: unscaled->Base scale uniformity

- **Evidence**: eff_x range [0.1500,0.1502] spread 0.103%; eff_y range [0.1500,0.1502] spread 0.103%; implied Base canvas ~ 1440x1350

- **Root cause**: A region composite is world-aligned iff the per-level unscaled->Base scale is uniform; >0.5% spread would mean the stitched Base.png is geometrically distorted vs zmdmap.

- **Fix**: If a region ever fails, rebuild its composite from per-level images at the layout positions (Iter2 generator); map01/map02 currently pass (uniform).

- **Impact**: Non-uniform scale would make every position read off that Base.png wrong.

- **Non-expected changes**: Check is read-only; map01/map02 unchanged.

### [PASS] C2 — map02: unscaled->Base scale uniformity

- **Evidence**: eff_x range [0.1600,0.1601] spread 0.057%; eff_y range [0.1601,0.1601] spread 0.010%; implied Base canvas ~ 1632x2880

- **Root cause**: A region composite is world-aligned iff the per-level unscaled->Base scale is uniform; >0.5% spread would mean the stitched Base.png is geometrically distorted vs zmdmap.

- **Fix**: If a region ever fails, rebuild its composite from per-level images at the layout positions (Iter2 generator); map01/map02 currently pass (uniform).

- **Impact**: Non-uniform scale would make every position read off that Base.png wrong.

- **Non-expected changes**: Check is read-only; map01/map02 unchanged.

### [PASS] C3 — map01: templates Base.png == runtime

- **Evidence**: implied-by-transforms (1440, 1350); runtime (1440, 1350); templates (1440, 1350)

- **Root cause**: `assets/templates` carries a truncated Wuling Base.png (2016x1920 vs runtime 2976) and `maptracker_coordinate_transforms.json` lacks the newer levels (lv007/lv008), so the stale copy shadows the complete runtime one on the load path.

- **Fix**: Sync templates from runtime (local; PNGs are gitignored) AND make TemplateBackend load the authoritative set with precedence so a stale copy can never shadow it (Iter3).

- **Impact**: Queries landing in the truncated north zone / new levels have no matching template.

- **Non-expected changes**: After sync templates==runtime, so recognition outcomes equal loading runtime directly.

### [PASS] C3 — map01: transforms span the runtime composite

- **Evidence**: implied-by-transforms (1440, 1350); runtime (1440, 1350); templates (1440, 1350)

- **Root cause**: `assets/templates` carries a truncated Wuling Base.png (2016x1920 vs runtime 2976) and `maptracker_coordinate_transforms.json` lacks the newer levels (lv007/lv008), so the stale copy shadows the complete runtime one on the load path.

- **Fix**: Sync templates from runtime (local; PNGs are gitignored) AND make TemplateBackend load the authoritative set with precedence so a stale copy can never shadow it (Iter3).

- **Impact**: Queries landing in the truncated north zone / new levels have no matching template.

- **Non-expected changes**: After sync templates==runtime, so recognition outcomes equal loading runtime directly.

### [PASS] C5 — Map01Base: tile_mapping canvas 1440x1350 vs Base.png (1440, 1350)

- **Evidence**: tile_mapping 160-grid is cut from this Base.png

- **Root cause**: tile_mapping's 160-grid must overlay exactly the Base.png it was cut from; mismatch would mean the fine-search rects point at the wrong pixels.

- **Fix**: None needed (passes); if a future Base.png is rebuilt, tile_mapping must be re-cut too.

- **Impact**: Guard against Base.png / tile_mapping desynchronisation.

- **Non-expected changes**: Read-only.

### [PASS] C5 — Map02Base: tile_mapping canvas 2016x2976 vs Base.png (2016, 2976)

- **Evidence**: tile_mapping 160-grid is cut from this Base.png

- **Root cause**: tile_mapping's 160-grid must overlay exactly the Base.png it was cut from; mismatch would mean the fine-search rects point at the wrong pixels.

- **Fix**: None needed (passes); if a future Base.png is rebuilt, tile_mapping must be re-cut too.

- **Impact**: Guard against Base.png / tile_mapping desynchronisation.

- **Non-expected changes**: Read-only.


## Narrative

- **Scene/image difference (accuracy)**: the runtime Python path uses a coarse ONNX classifier (`cls.onnx`, 128×128) on a *hardcoded* minimap crop with no de-rotation, no scale normalisation and no dynamic bbox; upstream's accurate path is gradient-ZNCC template matching at the correct 0.1625 minimap scale. Compounded by `assets/templates` shadowing the authoritative runtime templates with truncated / wrong-scale copies (C8).
- **Map spec vs big world**: per-level MapTracker images and ValleyIV `Base.png` ARE world-aligned (0.1625 and 0.15 of the zmdmap layout respectively; C2 PASS for map01), but other regions' stitched `Base.png` may be non-uniformly scaled (C2) and the templates copy is truncated (C3). Three mutually-inconsistent numeric frames exist in code: the 600-unit layout grid, the 160-px classifier grid, and grid-units from `grid_tiers`; `_parse_tile` mixes them so reported coordinates are not in the space `EntityDatabase.find_nearby` compares (entity `map_location`) — see C6.
- **Avoid duplication / missing coverage**: classifier covers only ~72% (Map01Base) / ~51% (Map02Base) of its own grid (C4); `assets/templates` duplicates the runtime assets but out-of-date (C8). The upstream de-duplication of overlapping *levels* (max-flow `distinguish_levels`) is already baked into the per-level images, so a layout-accurate composite does not double-cover overlaps.
- **Non-expected changes of the planned fixes**: code fixes are logic-only and unit-tested; image reconstruction is additive (new filename) and never overwrites the shipped `Base.png`, so the ONNX classifier (trained on the current MapLocator frame) is not desynchronised. Re-pointing the ONNX path at a new composite would require retraining in the external MaaEnd-AI repo — out of scope here; we instead stage the consistent tile set + mapping for it.
