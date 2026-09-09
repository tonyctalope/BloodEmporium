"""Patch the pinned YOLOv5-OBB checkout for CPU inference on Linux."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = "b00c3f245e50e7a80460a1b949d22ea7dfeb27a0"


def main():
    vendor = ROOT / "yolov5_obb"
    revision = subprocess.check_output(["git", "-C", str(vendor), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        raise SystemExit(f"Expected YOLOv5-OBB {REVISION}, found {revision}")
    (vendor / "utils/nms_rotated/__init__.py").write_text(
        "# Blood Emporium Linux: CPU implementation, no compiled CUDA extension.\n"
        "from backend.rotated_nms import obb_nms\n")
    # The upstream import downloads Arial even though inference never draws labels.
    plots = vendor / "utils/plots.py"
    text = plots.read_text()
    anchor = '    if RANK in (-1, 0):\n        check_font()  # download TTF if necessary'
    marker = '    # Blood Emporium: no font download on import.'
    if anchor not in text and marker not in text:
        raise SystemExit("YOLO font patch anchor changed")
    plots.write_text(text.replace(anchor, marker))
    print("YOLOv5-OBB Linux CPU support prepared")


if __name__ == "__main__":
    main()
