#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ! -x .venv/bin/python ]]; then
    echo 'Run ./setup-linux.sh first.' >&2
    exit 1
fi
# OpenCV's bundled Qt plugin conflicts with PyQt5. Use the PyQt5 plugin directory.
export QT_QPA_PLATFORM_PLUGIN_PATH="$PWD/.venv/lib/python3.10/site-packages/PyQt5/Qt5/plugins"
export QT_QPA_PLATFORM=xcb
export YOLO_CONFIG_DIR="$PWD/.cache/ultralytics"
export YOLOV5_CONFIG_DIR="$PWD/.cache/ultralytics"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
mkdir -p logs output "$YOLO_CONFIG_DIR" "$MPLCONFIGDIR"
exec .venv/bin/python main.py "$@"
