"""Applies the three site-packages patches the app needs, documented in backend/state.py (MODULE PATCHES).

The upstream author hand-edits their venv and never automated it, so a clean pip install produces a build
that crashes at the first prediction. Each patch targets an exact anchor from the pinned versions
(ultralytics 8.0.33, torch 1.13.1) and fails loudly if the anchor is missing, so a version bump cannot
silently reintroduce the bugs. Idempotent: re-running on patched files is a no-op.

1. ultralytics/hub/utils.py - disable the Traces telemetry (an HTTPS POST to api.ultralytics.com on a
   rate limit of seconds, attempted for every bloodweb capture).
2. ultralytics/yolo/engine/predictor.py - force verbose off in BasePredictor. verbose defaults to on, and
   the verbose path builds an Annotator over our screenshot, which asserts on non-contiguous images:
       AssertionError: Image not contiguous. Apply np.ascontiguousarray(im) to Annotator() input images.
3. torch/nn/modules/upsampling.py - the edges model was pickled under an older torch whose Upsample had no
   recompute_scale_factor attribute; torch >= 1.11 reads it in forward() and dies with AttributeError
   (https://github.com/ultralytics/yolov5/issues/6948#issuecomment-1075528897).

Usage: python packaging/patch_vendored.py <site-packages directory>
"""
import sys
from pathlib import Path

MARKER = "# BloodEmporium patch (see backend/state.py MODULE PATCHES)"

PATCHES = [
    (
        "ultralytics/hub/utils.py",
        "        self.enabled = SETTINGS['sync'] and \\",
        f"        self.enabled = False  {MARKER}\n"
        "        _upstream_enabled = SETTINGS['sync'] and \\",
    ),
    (
        "ultralytics/yolo/engine/predictor.py",
        "        self.args = get_cfg(cfg, overrides)",
        "        self.args = get_cfg(cfg, overrides)\n"
        f"        self.args.verbose = False  {MARKER}",
    ),
    (
        "torch/nn/modules/upsampling.py",
        "                             recompute_scale_factor=self.recompute_scale_factor)",
        f"                             recompute_scale_factor=getattr(self, 'recompute_scale_factor', None))  {MARKER}",
    ),
]


def main(site_packages):
    root = Path(site_packages)
    for relative_path, anchor, replacement in PATCHES:
        path = root / relative_path
        text = path.read_text(encoding="utf-8")
        if MARKER in text:
            print(f"already patched: {relative_path}")
            continue
        if text.count(anchor) != 1:
            raise SystemExit(f"anchor found {text.count(anchor)} times (expected 1) in {path} - "
                             f"the pinned version changed, re-verify the patch:\n{anchor}")
        path.write_text(text.replace(anchor, replacement), encoding="utf-8")
        print(f"patched: {relative_path}")


if __name__ == "__main__":
    main(sys.argv[1])
