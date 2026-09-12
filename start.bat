@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM  Hojo-TTS-Light-40M  Windows 启动脚本
REM  自动检测虚拟环境和依赖，有则直接启动，无则安装后启动
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

set VENV_DIR=venv
set PYTHON_BIN=python
if "%HOST%"=="" set HOST=0.0.0.0
if "%PORT%"=="" set PORT=7860

echo ============================================
echo   Hojo-TTS-Light-40M  WebUI + OpenAI API
echo ============================================

REM --- 1. 检测 Python ---
where %PYTHON_BIN% >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 python，请先安装 Python 3.10+
    echo   下载地址: https://www.python.org/downloads/
    echo   安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('%PYTHON_BIN% --version 2^>^&1') do echo [信息] Python: %%i

REM --- 2. 检测/创建虚拟环境 ---
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [步骤] 创建虚拟环境 venv ...
    %PYTHON_BIN% -m venv %VENV_DIR%
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo [步骤] 虚拟环境创建完成
) else (
    echo [信息] 虚拟环境已存在，跳过创建
)

REM --- 3. 激活虚拟环境 ---
call "%VENV_DIR%\Scripts\activate.bat"

REM --- 4. 检测依赖是否已安装 ---
echo [步骤] 检查依赖...
set DEPS_INSTALLED=true
for %%P in (numpy soundfile tokenizers onnxruntime flask) do (
    python -c "import %%P" >nul 2>&1
    if errorlevel 1 (
        echo   [缺失] %%P
        set DEPS_INSTALLED=false
    ) else (
        echo   [OK]   %%P
    )
)

REM --- 5. 安装缺失依赖 ---
if "%DEPS_INSTALLED%"=="false" (
    echo [步骤] 安装依赖 ...
    python -m pip install --upgrade pip -q
    python -m pip install numpy soundfile tokenizers onnxruntime flask
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
    echo [步骤] 依赖安装完成
) else (
    echo [信息] 所有依赖已安装，跳过安装
)

REM --- 6. 检测模型文件 ---
echo [步骤] 检查模型文件...
set MODEL_OK=true
for %%F in (
    "models\Hojo-TTS-Light-40M-llm.onnx"
    "models\Hojo-TTS-Light-40M-fine_local.onnx"
    "models\Hojo-TTS-Light-40M-decoder.onnx"
    "models\Hojo-TTS-Light-40M-voice.npz"
    "models\tokenizer.json"
    "models\config.json"
) do (
    if not exist %%F (
        echo   [缺失] %%~F
        set MODEL_OK=false
    )
)
if "%MODEL_OK%"=="false" (
    echo.
    echo [警告] 部分模型文件缺失！
    echo   请确保 models\ 目录完整
    echo.
    set /p CONTINUE=仍然继续启动? (y/N^): 
    if /i not "!CONTINUE!"=="y" exit /b 1
) else (
    echo   [OK] 模型文件完整
)

REM --- 7. 启动 ---
echo.
echo ============================================
echo   启动服务...
echo   WebUI:     http://127.0.0.1:%PORT%
echo   站内API:   POST http://127.0.0.1:%PORT%/api/tts
echo   OpenAIAPI: POST http://127.0.0.1:%PORT%/v1/audio/speech
echo   按 Ctrl+C 停止
echo ============================================
echo.

python app.py --host %HOST% --port %PORT%

pause
