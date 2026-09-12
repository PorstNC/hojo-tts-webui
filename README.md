# Hojo-TTS-Light-40M WebUI + OpenAI 兼容 API
English doc 英语文档 [File/文件](https://github.com/PorstNC/hojo-tts-webui/blob/main/README.en.md)

基于 [HojoAI/Hojo-TTS-Light](https://github.com/HojoAI/Hojo-TTS-Light) 的轻量级中英文语音合成服务。模型已预转换为 FP32 ONNX 格式，无需 PyTorch，CPU 即可运行。同时提供 Web 界面、站内 API 和 OpenAI 兼容 TTS 接口。

## 特性

- **15 个内置音色** — 2 个中文女声 + 13 个英文音色
- **中英文混合** — 单模型支持无缝中英合成
- **纯 ONNX Runtime** — 无需 GPU、无需 PyTorch
- **Web 界面** — Flask 后端 + 响应式前端，手机/电脑均可使用
- **OpenAI 兼容 API** — `POST /v1/audio/speech`，可直接用 OpenAI SDK 调用
- **模型登记** — 模型注册为 `hojo-tts-light-40m`，`GET /v1/models` 可查
- **多 API 密钥** — WebUI 设置面板可视化管理，支持添加/删除/重命名
- **计费模式切换** — WebUI 滑块三选一：关闭计费 / 按次计费 / 按Token计费，互斥即时生效
- **按次计费** — 每个密钥可设调用次数上限（-1=无限），自动扣减，超额返回 429
- **Token 计费** — 按输入文本 Token 数扣减，支持 1/百/千/万/亿 Token 档位，超额返回指定提示
- **用量统计** — 实时显示每个密钥的按次和 Token 用量，可分别一键重置
- **默认音色** — OpenAI 接口默认使用 `hojo_zh_f_02`（中文女声2）
- **跨平台** — Windows / Linux 一键启动脚本，自动检测依赖
- **多语言界面** — 英文 / 中文界面切换，语言文件放在 `locales/` 目录
- **自动模型下载** — 启动脚本自动检测模型，缺失时交互选择区域从 HuggingFace 下载
- **GPU/CPU 自适应** — 启动时选择 GPU（onnxruntime-gpu）或 CPU（onnxruntime）运行时

## 硬件要求

| 平台 | 最低内存 | 推荐内存 | 速度参考 |
|------|---------|---------|---------|
| Windows / Linux x86 | 1 GB RAM | 2 GB+ RAM | RTF ~0.3-0.7× (多线程) |
| Termux (Android) | 2 GB RAM | 4 GB+ RAM | RTF ~1-3× (取决于 CPU) |

> RTF = 生成耗时 ÷ 音频时长，<1 表示比实时更快。

## 快速开始

### Linux / Termux

```bash
git clone https://github.com/PorstNC/hojo-tts-webui.git
cd hojo-tts-webui
bash start.sh
```

脚本自动执行：创建虚拟环境 → 安装基础依赖 → 选择 GPU/CPU 运行时 → 检测模型（缺失则交互选择区域下载）→ 启动服务。

### Windows

双击 `start.bat`，或命令行：

```cmd
cd hojo-tts-webui
start.bat
```

### 手动安装（不使用脚本）

```bash
python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install onnxruntime      # CPU 版；GPU 用户用 pip install onnxruntime-gpu
python3 app.py --host 0.0.0.0 --port 7860
```

启动后访问：
- **WebUI**: http://127.0.0.1:7860
- **站内API**: `POST http://127.0.0.1:7860/api/tts`
- **OpenAI API**: `POST http://127.0.0.1:7860/v1/audio/speech`

## 模型下载

> 本仓库不包含模型权重（约 330MB），启动脚本会自动检测并下载。

### 自动下载（推荐）

运行 `start.sh` 或 `start.bat`，当检测到模型文件缺失时，会交互询问：

1. **选择区域**：
   - `1. China` — 使用 HF 镜像站（hf-mirror.com），国内速度快
   - `2. Other countries` — 使用 HF 官网（huggingface.co）

2. **选择运行时**：
   - `1. CPU` — 安装 `onnxruntime`，所有设备通用
   - `2. GPU` — 安装 `onnxruntime-gpu`，需要 NVIDIA GPU + CUDA

模型仓库：`HojoAI/Hojo-TTS-Light-40M`

### 手动下载

如果自动下载失败，可以手动下载：

```bash
pip install huggingface_hub

# 国内用户（镜像站）
export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download HojoAI/Hojo-TTS-Light-40M --local-dir ./models

# 海外用户（官网）
huggingface-cli download HojoAI/Hojo-TTS-Light-40M --local-dir ./models
```

下载完成后，目录结构应为：

```
hojo-tts-webui/
└── models/
    ├── Hojo-TTS-Light-40M-decoder.onnx
    ├── Hojo-TTS-Light-40M-fine_local.onnx
    ├── Hojo-TTS-Light-40M-llm.onnx
    ├── Hojo-TTS-Light-40M-voice.npz
    ├── tokenizer.json
    ├── tokenizer_config.json
    └── config.json
```

## 项目结构

```
hojo-tts-webui/
├── app.py                  # 主程序 (WebUI + 站内API + OpenAI兼容API)
├── infer.py                # TTS 高层 API (官方)
├── onnx_model.py           # ONNX 推理引擎 (官方)
├── config.json             # 配置文件 (模型名/默认音色/API密钥/音色映射)
├── requirements.txt        # Python 基础依赖 (不含 onnxruntime)
├── start.sh                # Linux 一键启动 (自动下载模型+GPU/CPU选择)
├── start.bat               # Windows 一键启动 (自动下载模型+GPU/CPU选择)
├── locales/                # 多语言文件 (en.json, zh.json)
├── models/                 # 模型文件 (启动时自动下载)
├── templates/index.html    # 前端页面
├── static/                 # CSS + JS
└── outputs/                # 生成的音频 (运行时创建)
```

## 配置文件 (config.json)

```json
{
  "model_name": "hojo-tts-light-40m",
  "default_voice": "hojo_zh_f_02",
  "admin_password": "",
  "api_keys": [],
  "openai_voice_map": {
    "alloy": "hojo_en_m_02",
    "echo": "hojo_en_m_01",
    "fable": "hojo_en_f_01",
    "onyx": "hojo_en_m_03",
    "nova": "hojo_en_f_02",
    "shimmer": "hojo_en_f_03"
  }
}
```

| 字段 | 说明 |
|------|------|
| `model_name` | 注册到 OpenAI 接口的模型 ID |
| `default_voice` | OpenAI 接口默认音色（默认 `hojo_zh_f_02` 中文女声2） |
| `admin_password` | 管理面板密码，为空则仅本机（127.0.0.1）可管理 |
| `api_keys` | API 密钥列表（对象数组），为空则免认证 |
| `openai_voice_map` | OpenAI 风格 voice 名到本模型音色 ID 的映射 |

### WebUI 可视化管理（推荐）

启动服务后，点击页面顶部 **"设置 · API密钥"** 标签页，即可：

- **添加密钥** — 填写名称、按次额度、Token 额度（均支持 -1=无限），可自动生成随机密钥
- **Token 快捷档位** — 一键设置 1 Token / 百 / 千 / 万 / 亿 / 无限
- **查看用量** — 每个密钥分别显示按次额度/已用/剩余 和 Token额度/已用Token/剩余Token
- **修改额度** — 分别调整按次额度和 Token 额度上限
- **重置用量** — 分别重置按次用量和 Token 用量
- **重命名** — 修改密钥显示名称
- **删除** — 移除密钥
- **复制密钥** — 一键复制完整密钥到剪贴板

> 未设置 `admin_password` 时，仅本机访问可管理；设置后需输入密码。

### 手动编辑 config.json（备选）

`api_keys` 支持对象数组格式（含按次和 Token 额度统计）：

```json
"api_keys": [
  {"key": "sk-my-key-001", "name": "项目A", "quota": -1, "used": 0, "token_quota": -1, "tokens_used": 0, "created_at": "2026-09-12 10:00:00"},
  {"key": "sk-my-key-002", "name": "项目B", "quota": 1000, "used": 0, "token_quota": 100000, "tokens_used": 0, "created_at": "2026-09-12 10:05:00"}
]
```

- `quota`: -1=无限调用，正数=最大调用次数（按次计费）
- `used`: 已成功调用次数（系统自动维护）
- `token_quota`: -1=无限，正数=最大 Token 数（Token 计费）
- `tokens_used`: 已消耗 Token 数（系统自动维护）
- 按次额度用完返回 **429 quota_exceeded**
- Token 额度用完返回 **429 token_quota_exceeded**，提示："文本转语音模型额度已用完 请进行续费或者购买Pro版 或者联系你的模型提供商"

重启服务后生效。站内 API（`/api/tts`）始终免密钥；OpenAI 接口（`/v1/*`）需认证。

### 计费模式（三选一，互斥）

在 WebUI 设置面板顶部可切换，或通过 API 管理：

```bash
# 查看当前模式
curl http://localhost:7860/api/admin/billing-mode

# 设置计费模式
curl -X POST http://localhost:7860/api/admin/billing-mode \
  -H "Content-Type: application/json" \
  -d '{"billing_mode":"per_token"}'
```

| 模式 | 说明 |
|------|------|
| `none` | 关闭计费，所有有效密钥无限调用，不扣减任何额度 |
| `per_call` | 按次计费，每次成功合成扣减 1 次（`quota` 字段） |
| `per_token` | 按 Token 计费，按输入文本实际 Token 数扣减（`token_quota` 字段） |

> 切换即时生效，无需重启。config.json 中 `billing_mode` 字段持久化。

## API 接口文档

### 1. 站内 TTS (免密钥)

```
POST /api/tts
Content-Type: application/json

{
  "text": "要合成的文本",
  "voice": "hojo_zh_f_02"
}
```

返回：`audio/wav` 二进制音频流。

### 2. OpenAI 兼容 — 模型列表

```
GET /v1/models
Authorization: Bearer <api_key>   (如果配置了密钥)
```

返回：
```json
{
  "object": "list",
  "data": [{
    "id": "hojo-tts-light-40m",
    "object": "model",
    "owned_by": "hojo-tts-local"
  }]
}
```

### 3. OpenAI 兼容 — 语音合成

```
POST /v1/audio/speech
Content-Type: application/json
Authorization: Bearer <api_key>   (如果配置了密钥)

{
  "model": "hojo-tts-light-40m",
  "input": "要合成的文本",
  "voice": "hojo_zh_f_02",
  "response_format": "wav",
  "speed": 1.0
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | 是 | 模型 ID，`hojo-tts-light-40m` |
| `input` | string | 是 | 要合成的文本（最长 4096 字符） |
| `voice` | string | 否 | 音色 ID 或 OpenAI 风格名（alloy/echo/fable/onyx/nova/shimmer），默认 `hojo_zh_f_02` |
| `response_format` | string | 否 | `wav`（默认）、`mp3`（需 pydub+ffmpeg） |
| `speed` | float | 否 | 语速 0.25-4.0，默认 1.0 |

返回：音频二进制流。

### curl 调用示例

```bash
# 免密钥（默认配置）
curl -X POST http://127.0.0.1:7860/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"hojo-tts-light-40m","input":"你好，世界","voice":"hojo_zh_f_02"}' \
  --output output.wav

# 带密钥
curl -X POST http://127.0.0.1:7860/v1/audio/speech \
  -H "Authorization: Bearer sk-my-key-001" \
  -H "Content-Type: application/json" \
  -d '{"model":"hojo-tts-light-40m","input":"Hello world"}' \
  --output output.wav
```

### Python (OpenAI SDK) 调用

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:7860/v1",
    api_key="sk-my-key-001",  # 免密钥时随便填
)

response = client.audio.speech.create(
    model="hojo-tts-light-40m",
    voice="hojo_zh_f_02",
    input="你好，这是通过 OpenAI SDK 调用的本地 TTS。",
)
response.stream_to_file("output.wav")
```

## 音色列表

| 音色 ID | 语言 | 性别 | 说明 |
|---------|------|------|------|
| `hojo_zh_f_01` | 中文 | 女 | 中文女声 1 |
| `hojo_zh_f_02` | 中文 | 女 | **中文女声 2（OpenAI 默认）** |
| `hojo_en_f_01` ~ `08` | English | Female | 英文女声 1-8 |
| `hojo_en_m_01` ~ `05` | English | Male | 英文男声 1-5 |
| `hojo_en_u_01` | English | — | 英文音色 U1 |

## 命令行参数

```bash
python3 app.py [选项]

选项:
  --host HOST        绑定地址 (默认: 0.0.0.0)
  --port PORT        绑定端口 (默认: 7860)
  --no-preload       首次请求时才加载模型 (节省启动内存)
  --debug            Flask 调试模式
```

环境变量：
```bash
PORT=8080 HOST=127.0.0.1 bash start.sh
```

## 多语言界面

WebUI 支持英文和中文界面切换。语言文件放在 `locales/` 目录：

- `locales/en.json` — 英文翻译
- `locales/zh.json` — 中文翻译

在页面右上角使用语言选择器切换，选择保存在 localStorage 中，跨会话持久化。

添加新语言：
1. 复制 `locales/en.json` 为 `locales/<lang>.json`
2. 翻译所有值
3. 在 `templates/index.html` 的 `<select id="langSelect">` 中添加语言选项

## 性能优化

- **x86 Linux/Windows**：自动使用全部 CPU 核心，多线程加速
- **Termux/ARM**：自动限制为 `核数-1` 线程，避免手机过热卡死
- 模型加载约需 4-10 秒（取决于磁盘速度）
- 运行时内存约 750MB-1.2GB

## 常见问题

**Q: 启动后访问页面空白或 500？**
A: 查看终端报错，通常是模型文件缺失。确保 `models/` 目录完整，或重新运行 `start.sh` 自动下载。

**Q: OpenAI 接口返回 401？**
A: `config.json` 中配置了 `api_keys`，请求需带 `Authorization: Bearer <密钥>`。或将 `api_keys` 设为 `[]` 关闭认证。

**Q: 如何更换默认音色？**
A: 修改 `config.json` 中的 `default_voice` 字段，重启服务。

**Q: mp3 格式输出失败？**
A: mp3 需要 `pydub` 和 `ffmpeg`。安装：`pip install pydub` 并确保系统有 ffmpeg。或直接用默认的 wav 格式。

**Q: Termux 上 onnxruntime 安装失败？**
A: 推荐使用 proot-distro Ubuntu 环境，或在原生 Termux 中尝试 `pkg install onnxruntime`（TUR 仓库）。

**Q: 模型下载很慢或失败？**
A: 国内用户选择 `1. China` 使用镜像站；海外用户选择 `2. Other countries`。也可以手动用 `huggingface-cli download` 下载。

**Q: GPU 版本运行报错？**
A: 确保安装了 CUDA 和 cuDNN，且 `onnxruntime-gpu` 版本与 CUDA 版本匹配。不确定时选择 CPU 版本。

## 许可证

- 模型代码：Apache License 2.0 (HojoAI)
- 本项目 WebUI/API 层：MIT License
