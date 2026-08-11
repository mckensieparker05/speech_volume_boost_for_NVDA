# -*- coding: utf-8 -*-
"""Package the Speech Volume Boost add-on into a .nvda-addon file.

Usage:  python build.py
Output: dist/speechVolumeBoost-<version>.nvda-addon (relative to this script)
"""

import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(HERE, "src")
DIST_DIR = os.path.join(HERE, "dist")
MANIFEST = os.path.join(SRC_DIR, "manifest.ini")

EXCLUDED_DIRS = {"__pycache__", ".git"}
EXCLUDED_EXTENSIONS = {".pyc", ".pyo"}
MANIFEST_FIELDS = {"name", "version"}


def read_manifest():
	values = {}
	with open(MANIFEST, "r", encoding="utf-8") as f:
		for line in f:
			line = line.strip()
			if not line or line.startswith("#") or "=" not in line:
				continue
			key, value = line.split("=", 1)
			key = key.strip().lower()
			value = value.strip().strip('"').strip()
			values[key] = value
	return values


def collect_files(root):
	paths = []
	for dirpath, dirnames, filenames in os.walk(root):
		dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
		for filename in filenames:
			if os.path.splitext(filename)[1].lower() in EXCLUDED_EXTENSIONS:
				continue
			paths.append(os.path.join(dirpath, filename))
	return paths


def main():
	manifest = read_manifest()
	missing = MANIFEST_FIELDS - set(manifest)
	if missing:
		raise SystemExit(f"manifest.ini is missing required fields: {', '.join(sorted(missing))}")
	version = manifest["version"]
	filename = f"{manifest['name']}-{version}.nvda-addon"
	output = os.path.join(DIST_DIR, filename)
	os.makedirs(DIST_DIR, exist_ok=True)
	files = collect_files(SRC_DIR)
	with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
		for filepath in files:
			relpath = os.path.relpath(filepath, SRC_DIR).replace("\\", "/")
			zf.write(filepath, relpath)
	print(f"Created {output} with {len(files)} files")


if __name__ == "__main__":
	main()
