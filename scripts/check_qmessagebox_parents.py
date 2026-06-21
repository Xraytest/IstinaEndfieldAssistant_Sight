#!/usr/bin/env python3
"""
Small static checker to find QMessageBox.* calls that may not pass a parent widget as first argument.
Run from repository root (IstinaEndfieldAssistant folder).
"""
import re
import os

PAT = re.compile(r"QMessageBox\.(information|warning|critical|question)\s*\(")

def check_file(path):
    res = []
    with open(path, 'r', encoding='utf-8') as f:
        txt = f.read()
    for m in PAT.finditer(txt):
        start = m.start()
        # Extract up to closing parenthesis - crude heuristic: take next 200 chars
        snippet = txt[start:start+200]
        # If snippet starts with QMessageBox.<fn>(self, -> good
        if re.match(r"QMessageBox\.(?:information|warning|critical|question)\s*\(\s*self\s*,", snippet):
            continue
        # If snippet contains _get_parent or _get_parent( -> acceptable
        if "_get_parent" in snippet:
            continue
        # Otherwise record
        lineno = txt.count('\n', 0, start) + 1
        res.append((lineno, snippet.replace('\n', ' ')))
    return res

if __name__ == '__main__':
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    matches = {}
    for dirpath, dirs, files in os.walk(root):
        for fname in files:
            if not fname.endswith('.py'):
                continue
            path = os.path.join(dirpath, fname)
            if 'site-packages' in path or '.venv' in path:
                continue
            try:
                found = check_file(path)
                if found:
                    matches[path] = found
            except Exception:
                pass
    if not matches:
        print('No suspicious QMessageBox calls found.')
    else:
        for path, items in matches.items():
            print(f'File: {path}')
            for lineno, snip in items:
                print(f'  Line {lineno}: {snip}')
            print()
