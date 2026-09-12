#!/usr/bin/env bash
# ============================================================
# Hojo-TTS-Light-40M  Linux / Termux Launcher
# - Auto-detect venv + dependencies
# - Python 3.10+ version check
# - Auto-download model from HuggingFace (mirror or official)
# - Model integrity verification
# - GPU (onnxruntime-gpu) / CPU (onnxruntime) runtime choice
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="venv"
PYTHON_BIN="python3"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-7860}"
MODEL_REPO="HojoAI/Hojo-TTS-Light-40M"

echo "============================================"
echo "  Hojo-TTS-Light-40M  WebUI + OpenAI API"
echo "============================================"

# --- 1. Check Python ---
if ! command -v $PYTHON_BIN &>/dev/null; then
    echo "[ERROR] python3 not found. Please install Python 3.10+"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "  Termux:        pkg install python"
    exit 1
fi

PY_VER=$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON_BIN -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON_BIN -c "import sys; print(sys.version_info.minor)")
echo "[INFO] Python version: $PY_VER"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "[ERROR] Python 3.10+ is required. You have Python $PY_VER."
    echo "  Please upgrade Python to 3.10 or higher."
    exit 1
fi
echo "[INFO] Python 3.10+ check passed"

# --- 2. Create / detect venv ---
if [ ! -d "$VENV_DIR" ]; then
    echo "[STEP] Creating virtual environment venv ..."
    $PYTHON_BIN -m venv "$VENV_DIR"
    echo "[STEP] Virtual environment created"
else
    echo "[INFO] Virtual environment exists, skipping"
fi

# --- 3. Activate venv ---
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# --- 4. Install base dependencies ---
echo "[STEP] Installing base dependencies ..."
pip install --upgrade pip -q
pip install -r requirements.txt
echo "[STEP] Base dependencies installed"

# --- 5. Check / install onnxruntime (GPU or CPU) ---
RUNTIME_INSTALLED=false
if python3 -c "import onnxruntime" 2>/dev/null; then
    echo "[INFO] onnxruntime already installed"
    RUNTIME_INSTALLED=true
elif python3 -c "import onnxruntime_gpu" 2>/dev/null; then
    echo "[INFO] onnxruntime-gpu already installed"
    RUNTIME_INSTALLED=true
fi

if [ "$RUNTIME_INSTALLED" = false ]; then
    echo ""
    echo "============================================"
    echo "  Choose ONNX Runtime:"
    echo "    1. CPU  (onnxruntime)       — works everywhere, Python 3.10+"
    echo "    2. GPU  (onnxruntime-gpu)   — requires NVIDIA GPU + CUDA 12.x"
    echo "       (NOT available on Termux/Android-ARM or macOS)"
    echo "============================================"
    read -rp "Enter your choice [1/2] (default 1): " rt_choice
    case "$rt_choice" in
        2)
            echo "[STEP] Installing onnxruntime-gpu ..."
            pip install onnxruntime-gpu
            echo "[STEP] onnxruntime-gpu installed"
            ;;
        *)
            echo "[STEP] Installing onnxruntime (CPU) ..."
            pip install "onnxruntime>=1.19,<1.31"
            echo "[STEP] onnxruntime (CPU) installed"
            ;;
    esac
fi

# --- 6. Check model files ---
echo "[STEP] Checking model files ..."
MODEL_OK=true
for f in \
    "models/Hojo-TTS-Light-40M-llm.onnx" \
    "models/Hojo-TTS-Light-40M-fine_local.onnx" \
    "models/Hojo-TTS-Light-40M-decoder.onnx" \
    "models/Hojo-TTS-Light-40M-voice.npz" \
    "models/tokenizer.json" \
    "models/config.json"; do
    if [ ! -f "$f" ]; then
        echo "  [MISSING] $f"
        MODEL_OK=false
    fi
done

if [ "$MODEL_OK" = false ]; then
    echo ""
    echo "============================================"
    echo "  Model files not found. Download from HuggingFace."
    echo "  NOTE: The HF repo ($MODEL_REPO) already contains"
    echo "  pre-converted FP32 ONNX models — no conversion needed."
    echo ""
    echo "  Select your region:"
    echo "    1. China           — use HF mirror (hf-mirror.com)"
    echo "    2. Other countries — use official HF (huggingface.co)"
    echo "============================================"
    read -rp "Enter your choice [1/2] (default 1): " region_choice

    mkdir -p models

    case "$region_choice" in
        2)
            echo "[STEP] Downloading from official HuggingFace ..."
            unset HF_ENDPOINT
            python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='$MODEL_REPO', local_dir='./models')
print('[STEP] Model download complete')
"
            ;;
        *)
            echo "[STEP] Downloading from HF mirror (hf-mirror.com) ..."
            export HF_ENDPOINT="https://hf-mirror.com"
            python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='$MODEL_REPO', local_dir='./models')
print('[STEP] Model download complete')
"
            ;;
    esac

    # Verify downloaded model integrity
    echo "[STEP] Verifying model integrity ..."
    MODEL_OK=true
    for f in \
        "models/Hojo-TTS-Light-40M-llm.onnx" \
        "models/Hojo-TTS-Light-40M-fine_local.onnx" \
        "models/Hojo-TTS-Light-40M-decoder.onnx" \
        "models/Hojo-TTS-Light-40M-voice.npz" \
        "models/tokenizer.json" \
        "models/config.json"; do
        if [ ! -f "$f" ]; then
            echo "  [MISSING] $f"
            MODEL_OK=false
        else
            SIZE=$(stat -c%s "$f" 2>/dev/null || echo "0")
            echo "  [OK] $f ($SIZE bytes)"
        fi
    done
    if [ "$MODEL_OK" = false ]; then
        echo "[ERROR] Model download incomplete. Please check network and retry."
        exit 1
    fi
    echo "  [OK] All model files verified"
else
    echo "  [OK] Model files complete"
fi

# --- 7. Start ---
echo ""
echo "============================================"
echo "  Starting service ..."
echo "  WebUI:     http://127.0.0.1:${PORT}"
echo "  Internal:  POST http://127.0.0.1:${PORT}/api/tts  (requires HMAC hash)"
echo "  OpenAI:    POST http://127.0.0.1:${PORT}/v1/audio/speech"
echo "  Press Ctrl+C to stop"
echo "============================================"
echo ""

exec python3 app.py --host "$HOST" --port "$PORT"
