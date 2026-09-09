#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/.python"
for cmd in python git tesseract; do
    command -v "$cmd" >/dev/null || { echo "Missing $cmd. See README.md." >&2; exit 1; }
done
if [[ -n ${WAYLAND_DISPLAY:-} ]]; then
    for cmd in hyprctl grim; do
        command -v "$cmd" >/dev/null || { echo "Missing $cmd. See README.md." >&2; exit 1; }
    done
fi
if [[ ! -x .bootstrap/bin/uv ]]; then
    python -m venv .bootstrap
    .bootstrap/bin/python -m pip install uv==0.12.11
fi
if [[ ! -x .venv/bin/python ]]; then
    .bootstrap/bin/uv venv --python 3.10 .venv
fi
.bootstrap/bin/uv pip install --python .venv/bin/python \
    'torch==1.13.1+cpu' 'torchvision==0.14.1+cpu' --index-url https://download.pytorch.org/whl/cpu
.bootstrap/bin/uv pip install --python .venv/bin/python -r requirements-linux.txt
revision=b00c3f245e50e7a80460a1b949d22ea7dfeb27a0
if [[ ! -d yolov5_obb ]]; then
    git clone https://github.com/hukaixuan19970627/yolov5_obb.git yolov5_obb
    git -C yolov5_obb checkout "$revision"
fi
.venv/bin/python packaging/patch_vendored.py .venv/lib/python3.10/site-packages
.venv/bin/python packaging/prepare_linux.py
mkdir -p logs output
echo 'Ready. Run ./run-linux.sh --selfcheck, then ./run-linux.sh'
