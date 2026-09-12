#!/usr/bin/env bash
# ============================================================
# Hojo-TTS-Light-40M  Linux 启动脚本
# 自动检测虚拟环境和依赖，有则直接启动，无则安装后启动
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="venv"
PYTHON_BIN="python3"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-7860}"

echo "============================================"
echo "  Hojo-TTS-Light-40M  WebUI + OpenAI API"
echo "============================================"

# --- 1. 检测 Python ---
if ! command -v $PYTHON_BIN &>/dev/null; then
    echo "[错误] 未找到 python3，请先安装 Python 3.10+"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "  CentOS/RHEL:   sudo yum install python3 python3-pip"
    echo "  Arch:          sudo pacman -S python python-pip"
    exit 1
fi
echo "[信息] Python: $($PYTHON_BIN --version)"

# --- 2. 检测/创建虚拟环境 ---
if [ ! -d "$VENV_DIR" ]; then
    echo "[步骤] 创建虚拟环境 venv ..."
    $PYTHON_BIN -m venv "$VENV_DIR"
    echo "[步骤] 虚拟环境创建完成"
else
    echo "[信息] 虚拟环境已存在，跳过创建"
fi

# --- 3. 激活虚拟环境 ---
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# --- 4. 检测依赖是否已安装 ---
echo "[步骤] 检查依赖..."
DEPS_INSTALLED=true
for pkg in numpy soundfile tokenizers onnxruntime flask; do
    if ! python3 -c "import $pkg" 2>/dev/null; then
        echo "  [缺失] $pkg"
        DEPS_INSTALLED=false
    else
        echo "  [OK]   $pkg"
    fi
done

# --- 5. 安装缺失依赖 ---
if [ "$DEPS_INSTALLED" = false ]; then
    echo "[步骤] 安装依赖 ..."
    pip install --upgrade pip -q
    pip install numpy soundfile tokenizers onnxruntime flask
    echo "[步骤] 依赖安装完成"
else
    echo "[信息] 所有依赖已安装，跳过安装"
fi

# --- 6. 检测模型文件 ---
echo "[步骤] 检查模型文件..."
MODEL_OK=true
for f in \
    "models/Hojo-TTS-Light-40M-llm.onnx" \
    "models/Hojo-TTS-Light-40M-fine_local.onnx" \
    "models/Hojo-TTS-Light-40M-decoder.onnx" \
    "models/Hojo-TTS-Light-40M-voice.npz" \
    "models/tokenizer.json" \
    "models/config.json"; do
    if [ ! -f "$f" ]; then
        echo "  [缺失] $f"
        MODEL_OK=false
    fi
done
if [ "$MODEL_OK" = false ]; then
    echo ""
    echo "[警告] 部分模型文件缺失！"
    echo "  请确保 models/ 目录完整，或运行以下命令下载："
    echo "  pip install huggingface_hub"
    echo "  python3 -c \"from huggingface_hub import snapshot_download; snapshot_download('HojoAI/Hojo-TTS-Light-40M', local_dir='./models')\""
    echo ""
    read -rp "仍然继续启动? (y/N) " ans
    [ "$ans" != "y" ] && exit 1
else
    echo "  [OK] 模型文件完整"
fi

# --- 7. 启动 ---
echo ""
echo "============================================"
echo "  启动服务..."
echo "  WebUI:     http://127.0.0.1:${PORT}"
echo "  站内API:   POST http://127.0.0.1:${PORT}/api/tts"
echo "  OpenAIAPI: POST http://127.0.0.1:${PORT}/v1/audio/speech"
echo "  按 Ctrl+C 停止"
echo "============================================"
echo ""

exec python3 app.py --host "$HOST" --port "$PORT"
