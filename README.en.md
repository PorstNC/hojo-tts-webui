# Hojo-TTS-Light-40M WebUI + OpenAI-Compatible API

A lightweight Chinese/English speech synthesis service based on [HojoAI/Hojo-TTS-Light](https://github.com/HojoAI/Hojo-TTS-Light). The model is pre-converted to FP32 ONNX format — no PyTorch required, runs on CPU. Includes a Web interface, internal API (HMAC hash authentication), and OpenAI-compatible TTS endpoint.

> **Requirement: Python 3.10+** (tested on 3.10 / 3.11 / 3.12)

## Features

- **15 built-in voices** — 2 Chinese female + 13 English voices
- **Mixed Chinese/English** — single model supports seamless CN/EN synthesis
- **Pure ONNX Runtime** — no GPU, no PyTorch needed
- **Web UI** — Flask backend + responsive frontend, works on mobile and desktop
- **OpenAI-compatible API** — `POST /v1/audio/speech`, works directly with OpenAI SDK
- **Internal API HMAC auth** — `POST /api/tts` requires X-Timestamp/X-Nonce/X-Hash signature, secret generated at startup and stored locally, replay protection
- **Model registration** — registered as `hojo-tts-light-40m`, queryable via `GET /v1/models`
- **Multiple API keys** — visual management in WebUI settings, support add/delete/rename
- **Billing mode switch** — WebUI slider three-way toggle: off / per-call / per-token, mutually exclusive, instant effect
- **Per-call billing** — each key can set call count limit (-1=unlimited), auto-decrement, 429 on excess
- **Token billing** — deduct by input text token count, supports 1/hundred/thousand/ten-thousand/hundred-million token tiers, custom prompt on excess
- **Auto rollback on failure** — quota deducted before synthesis; if synthesis fails, deduction is automatically rolled back so failed requests never burn quota
- **Usage statistics** — real-time per-call and token usage for each key, one-click reset separately
- **Default voice** — OpenAI endpoint defaults to `hojo_zh_f_02` (Chinese female 2)
- **Lock-free concurrent inference** — ONNX Runtime thread-safe, uses per-thread RNG, multiple requests run in parallel with no global lock
- **Fixed random seed** — seed=42, deterministic output for the same input text+voice, reproducible
- **Auto model download** — launcher auto-detects model, if missing interactively selects region (China mirror / international official) to download from HuggingFace
- **Cross-platform** — one-click launch scripts for Windows / Linux / Termux, auto dependency detection
- **Multi-language UI** — English / Chinese interface switch, language files in `locales/`

## Hardware Requirements

| Platform | Min RAM | Recommended RAM | Speed Reference |
|----------|---------|-----------------|-----------------|
| Windows / Linux x86 | 1 GB RAM | 2 GB+ RAM | RTF ~0.3-0.7× (multi-thread) |
| Termux (Android) | 2 GB RAM | 4 GB+ RAM | RTF ~1-3× (depends on CPU) |

> RTF = generation time ÷ audio duration, <1 means faster than real-time.

## Quick Start

> **Prerequisite: Python 3.10+** (tested on 3.10 / 3.11 / 3.12)

### Linux / Termux

```bash
git clone https://github.com/PorstNC/hojo-tts-webui.git
cd hojo-tts-webui
bash start.sh
```

The script automatically: Python version check → creates venv → installs base dependencies → chooses CPU/GPU runtime → checks model (downloads interactively from HuggingFace if missing) → verifies model integrity → starts service.

### Windows

Double-click `start.bat`, or from command line:

```cmd
cd hojo-tts-webui
start.bat
```

### Manual Install (without script)

```bash
python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install numpy soundfile tokenizers onnxruntime flask
python3 app.py --host 0.0.0.0 --port 7860
```

After launch, access:
- **WebUI**: http://127.0.0.1:7860
- **Internal API**: `POST http://127.0.0.1:7860/api/tts`
- **OpenAI API**: `POST http://127.0.0.1:7860/v1/audio/speech`

## Project Structure

```
hojo-tts-webui/
├── app.py                  # Main program (WebUI + internal API + OpenAI-compatible API)
├── infer.py                # TTS high-level API (official)
├── onnx_model.py           # ONNX inference engine (official)
├── config.json             # Config file (model name/default voice/API keys/voice map)
├── requirements.txt        # Python dependencies
├── start.sh                # Linux one-click launch (auto venv + dependency detection)
├── start.bat               # Windows one-click launch
├── locales/                # Multi-language files (en.json, zh.json)
├── models/                 # Model files (~330MB, pre-downloaded)
├── templates/index.html    # Frontend page
├── static/                 # CSS + JS
└── outputs/                # Generated audio (created at runtime)
```

## Configuration (config.json)

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

| Field | Description |
|-------|-------------|
| `model_name` | Model ID registered to OpenAI endpoint |
| `default_voice` | Default voice for OpenAI endpoint (default `hojo_zh_f_02` Chinese female 2) |
| `admin_password` | Admin panel password; empty means only localhost (127.0.0.1) can manage |
| `api_keys` | API key list (object array); empty means no auth required |
| `openai_voice_map` | Mapping from OpenAI-style voice names to model voice IDs |

### WebUI Visual Management (Recommended)

After launching, click the **"Settings · API Keys"** tab at the top to:

- **Add key** — enter name, per-call quota, token quota (all support -1=unlimited), auto-generate random key
- **Token quick tiers** — one-click set 1 Token / hundred / thousand / ten-thousand / hundred-million / unlimited
- **View usage** — each key shows per-call quota/used/remaining and token quota/used/remaining separately
- **Modify quota** — adjust per-call and token quota limits separately
- **Reset usage** — reset per-call and token usage separately
- **Rename** — modify key display name
- **Delete** — remove key
- **Copy key** — one-click copy full key to clipboard

> When `admin_password` is not set, only localhost access can manage; after setting, password is required.

### Manual Edit config.json (Alternative)

`api_keys` supports object array format (with per-call and token quota tracking):

```json
"api_keys": [
  {"key": "sk-my-key-001", "name": "Project A", "quota": -1, "used": 0, "token_quota": -1, "tokens_used": 0, "created_at": "2026-09-12 10:00:00"},
  {"key": "sk-my-key-002", "name": "Project B", "quota": 1000, "used": 0, "token_quota": 100000, "tokens_used": 0, "created_at": "2026-09-12 10:05:00"}
]
```

- `quota`: -1=unlimited calls, positive=max call count (per-call billing)
- `used`: successful call count (system auto-maintained)
- `token_quota`: -1=unlimited, positive=max token count (token billing)
- `tokens_used`: consumed token count (system auto-maintained)
- Per-call quota exhausted returns **429 quota_exceeded**
- Token quota exhausted returns **429 token_quota_exceeded**, prompt: "Text-to-speech model quota exhausted. Please renew or purchase Pro version or contact your model provider."

Restart service to apply. Internal API (`/api/tts`) always key-free; OpenAI endpoint (`/v1/*`) requires auth.

### Billing Mode (three-way, mutually exclusive)

Switch at the top of WebUI settings panel, or via API:

```bash
# View current mode
curl http://localhost:7860/api/admin/billing-mode

# Set billing mode
curl -X POST http://localhost:7860/api/admin/billing-mode \
  -H "Content-Type: application/json" \
  -d '{"billing_mode":"per_token"}'
```

| Mode | Description |
|------|-------------|
| `none` | Billing off, all valid keys unlimited calls, no quota deducted |
| `per_call` | Per-call billing, each successful synthesis deducts 1 call (`quota` field) |
| `per_token` | Token billing, deduct by actual input text token count (`token_quota` field) |

> Switch takes effect instantly, no restart needed. `billing_mode` field in config.json persists.

## API Documentation

### 1. Internal TTS (HMAC hash authentication)

The internal API requires a timestamped HMAC signature to prevent unauthorized access and replay attacks.

**Get the secret**: After admin login, call `GET /api/admin/internal-hash` to retrieve `internal_hash`.

**Required headers**:
```
X-Timestamp: Current Unix timestamp (seconds)
X-Nonce: Random string (unique per request, replay protection)
X-Hash: HMAC-SHA256(secret, "timestamp:nonce:sha256(body)")
```

**Request body**:
```json
{
  "text": "text to synthesize",
  "voice": "hojo_zh_f_02"
}
```

**Signature example (Python)**:
```python
import hmac, hashlib, time, secrets, json, requests

SECRET = "your_internal_hash"
ts = str(int(time.time()))
nonce = secrets.token_hex(16)
body = json.dumps({"text": "Hello", "voice": "hojo_zh_f_02"})
body_sha = hashlib.sha256(body.encode()).hexdigest()
sig = hmac.new(SECRET.encode(), f"{ts}:{nonce}:{body_sha}".encode(), hashlib.sha256).hexdigest()

resp = requests.post("http://127.0.0.1:7860/api/tts",
    headers={"X-Timestamp": ts, "X-Nonce": nonce, "X-Hash": sig, "Content-Type": "application/json"},
    data=body)
```

- Timestamp validity window: 300 seconds
- Nonce deduplication: last 4096 nonces cannot be reused
- Authentication failure returns 401

Returns: `audio/wav` binary audio stream.

### 2. OpenAI-Compatible — Model List

```
GET /v1/models
Authorization: Bearer <api_key>   (if keys configured)
```

Returns:
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

### 3. OpenAI-Compatible — Speech Synthesis

```
POST /v1/audio/speech
Content-Type: application/json
Authorization: Bearer <api_key>   (if keys configured)

{
  "model": "hojo-tts-light-40m",
  "input": "text to synthesize",
  "voice": "hojo_zh_f_02",
  "response_format": "wav",
  "speed": 1.0
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | yes | Model ID, `hojo-tts-light-40m` |
| `input` | string | yes | Text to synthesize (max 4096 chars) |
| `voice` | string | no | Voice ID or OpenAI-style name (alloy/echo/fable/onyx/nova/shimmer), default `hojo_zh_f_02` |
| `response_format` | string | no | `wav` (default), `mp3` (requires pydub+ffmpeg) |
| `speed` | float | no | Speed 0.25-4.0, default 1.0 |

Returns: audio binary stream.

### curl Example

```bash
# Key-free (default config)
curl -X POST http://127.0.0.1:7860/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"hojo-tts-light-40m","input":"Hello world","voice":"hojo_zh_f_02"}' \
  --output output.wav

# With key
curl -X POST http://127.0.0.1:7860/v1/audio/speech \
  -H "Authorization: Bearer sk-my-key-001" \
  -H "Content-Type: application/json" \
  -d '{"model":"hojo-tts-light-40m","input":"Hello world"}' \
  --output output.wav
```

### Python (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:7860/v1",
    api_key="sk-my-key-001",  # any value if key-free
)

response = client.audio.speech.create(
    model="hojo-tts-light-40m",
    voice="hojo_zh_f_02",
    input="Hello, this is local TTS called via OpenAI SDK.",
)
response.stream_to_file("output.wav")
```

## Voice List

| Voice ID | Language | Gender | Description |
|----------|----------|--------|-------------|
| `hojo_zh_f_01` | Chinese | Female | Chinese female 1 |
| `hojo_zh_f_02` | Chinese | Female | **Chinese female 2 (OpenAI default)** |
| `hojo_en_f_01` ~ `08` | English | Female | English female 1-8 |
| `hojo_en_m_01` ~ `05` | English | Male | English male 1-5 |
| `hojo_en_u_01` | English | — | English voice U1 |

## Command-Line Arguments

```bash
python3 app.py [options]

Options:
  --host HOST        Bind address (default: 0.0.0.0)
  --port PORT        Bind port (default: 7860)
  --no-preload       Load model on first request (saves startup memory)
  --debug            Flask debug mode
```

Environment variables:
```bash
PORT=8080 HOST=127.0.0.1 bash start.sh
```

## Performance Optimization

- **x86 Linux/Windows**: auto-use all CPU cores, multi-thread acceleration
- **Termux/ARM**: auto-limit to `cores-1` threads to avoid overheating
- Model load takes ~4-10 seconds (depends on disk speed)
- Runtime memory ~750MB-1.2GB

## FAQ

**Q: Blank page or 500 after launch?**
A: Check terminal errors, usually missing model files. Ensure `models/` directory is complete.

**Q: OpenAI endpoint returns 401?**
A: `api_keys` is configured in `config.json`, requests need `Authorization: Bearer <key>`. Or set `api_keys` to `[]` to disable auth.

**Q: How to change default voice?**
A: Modify `default_voice` field in `config.json`, restart service.

**Q: mp3 output fails?**
A: mp3 requires `pydub` and `ffmpeg`. Install: `pip install pydub` and ensure system has ffmpeg. Or use default wav format.

**Q: onnxruntime install fails on Termux?**
A: Recommended to use proot-distro Ubuntu environment, or try `pkg install onnxruntime` (TUR repo) in native Termux.

## Multi-Language UI

The WebUI supports English and Chinese interface switching. Language files are in `locales/`:

- `locales/en.json` — English translations
- `locales/zh.json` — Chinese translations

Use the language selector at the top-right of the page to switch. Selection is saved in localStorage and persists across sessions.

To add a new language:
1. Copy `locales/en.json` to `locales/<lang>.json`
2. Translate all values
3. Add the language option to the `<select id="langSelect">` in `templates/index.html`

## License

- Model code: Apache License 2.0 (HojoAI)
- This project's WebUI/API layer: MIT License
