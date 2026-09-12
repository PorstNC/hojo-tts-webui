@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM  Hojo-TTS-Light-40M  Windows Launcher
REM  Auto-detect venv + deps, download model if missing,
REM  choose GPU/CPU runtime, then start WebUI.
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

set VENV_DIR=venv
set PYTHON_BIN=python
if "%HOST%"=="" set HOST=0.0.0.0
if "%PORT%"=="" set PORT=7860
set MODEL_REPO=HojoAI/Hojo-TTS-Light-40M

echo ============================================
echo   Hojo-TTS-Light-40M  WebUI + OpenAI API
echo ============================================

REM --- 1. Check Python ---
where %PYTHON_BIN% >nul 2>&1
if errorlevel 1 (
    echo [ERROR] python not found. Please install Python 3.10+
    echo   Download: https://www.python.org/downloads/
    echo   Check "Add Python to PATH" during install
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('%PYTHON_BIN% --version 2^>^&1') do echo [INFO] Python: %%i

REM --- 2. Create / detect venv ---
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [STEP] Creating virtual environment venv ...
    %PYTHON_BIN% -m venv %VENV_DIR%
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [STEP] Virtual environment created
) else (
    echo [INFO] Virtual environment exists, skipping
)

REM --- 3. Activate venv ---
call "%VENV_DIR%\Scripts\activate.bat"

REM --- 4. Install base dependencies (without onnxruntime) ---
echo [STEP] Installing base dependencies ...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install base dependencies
    pause
    exit /b 1
)
echo [STEP] Base dependencies installed

REM --- 5. Check / install onnxruntime (GPU or CPU) ---
set RUNTIME_INSTALLED=false
python -c "import onnxruntime" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] onnxruntime already installed
    set RUNTIME_INSTALLED=true
)
python -c "import onnxruntime_gpu" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] onnxruntime-gpu already installed
    set RUNTIME_INSTALLED=true
)

if "%RUNTIME_INSTALLED%"=="false" (
    echo.
    echo ============================================
    echo   Choose ONNX Runtime:
    echo     1. CPU  (onnxruntime)       - works everywhere
    echo     2. GPU  (onnxruntime-gpu)   - requires NVIDIA GPU + CUDA
    echo ============================================
    set /p RT_CHOICE=Enter your choice [1/2] (default 1^): 
    if "!RT_CHOICE!"=="2" (
        echo [STEP] Installing onnxruntime-gpu ...
        python -m pip install onnxruntime-gpu
        if errorlevel 1 (
            echo [ERROR] Failed to install onnxruntime-gpu
            pause
            exit /b 1
        )
        echo [STEP] onnxruntime-gpu installed
    ) else (
        echo [STEP] Installing onnxruntime (CPU) ...
        python -m pip install onnxruntime
        if errorlevel 1 (
            echo [ERROR] Failed to install onnxruntime
            pause
            exit /b 1
        )
        echo [STEP] onnxruntime (CPU) installed
    )
)

REM --- 6. Check model files ---
echo [STEP] Checking model files ...
set MODEL_OK=true
if not exist "models\Hojo-TTS-Light-40M-llm.onnx" set MODEL_OK=false
if not exist "models\Hojo-TTS-Light-40M-fine_local.onnx" set MODEL_OK=false
if not exist "models\Hojo-TTS-Light-40M-decoder.onnx" set MODEL_OK=false
if not exist "models\Hojo-TTS-Light-40M-voice.npz" set MODEL_OK=false
if not exist "models\tokenizer.json" set MODEL_OK=false
if not exist "models\config.json" set MODEL_OK=false

if "%MODEL_OK%"=="false" (
    echo.
    echo ============================================
    echo   Model files not found. Download from HuggingFace.
    echo.
    echo   Select your region:
    echo     1. China           - use HF mirror (hf-mirror.com)
    echo     2. Other countries - use official HF (huggingface.co)
    echo ============================================
    set /p REGION_CHOICE=Enter your choice [1/2] (default 1^): 

    if not exist "models" mkdir models

    if "!REGION_CHOICE!"=="2" (
        echo [STEP] Downloading from official HuggingFace ...
        set HF_ENDPOINT=
        python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='%MODEL_REPO%', local_dir='./models'); print('[STEP] Model download complete')"
    ) else (
        echo [STEP] Downloading from HF mirror (hf-mirror.com) ...
        set HF_ENDPOINT=https://hf-mirror.com
        python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='%MODEL_REPO%', local_dir='./models'); print('[STEP] Model download complete')"
    )

    if errorlevel 1 (
        echo [ERROR] Model download failed. Please check network and retry.
        pause
        exit /b 1
    )

    REM Re-check after download
    echo [STEP] Re-checking model files ...
    set MODEL_OK=true
    if not exist "models\Hojo-TTS-Light-40M-llm.onnx" set MODEL_OK=false
    if not exist "models\Hojo-TTS-Light-40M-fine_local.onnx" set MODEL_OK=false
    if not exist "models\Hojo-TTS-Light-40M-decoder.onnx" set MODEL_OK=false
    if not exist "models\Hojo-TTS-Light-40M-voice.npz" set MODEL_OK=false
    if not exist "models\tokenizer.json" set MODEL_OK=false
    if not exist "models\config.json" set MODEL_OK=false

    if "%MODEL_OK%"=="false" (
        echo [ERROR] Model download incomplete. Please check network and retry.
        pause
        exit /b 1
    )
    echo   [OK] Model files complete
) else (
    echo   [OK] Model files complete
)

REM --- 7. Start ---
echo.
echo ============================================
echo   Starting service ...
echo   WebUI:     http://127.0.0.1:%PORT%
echo   Internal:  POST http://127.0.0.1:%PORT%/api/tts
echo   OpenAI:    POST http://127.0.0.1:%PORT%/v1/audio/speech
echo   Press Ctrl+C to stop
echo ============================================
echo.

python app.py --host %HOST% --port %PORT%

pause
