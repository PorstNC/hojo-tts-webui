#!/usr/bin/env python3
"""
Hojo-TTS-Light-40M WebUI + OpenAI-Compatible TTS API + Key Management

Features:
  - WebUI (browser interface) with Settings panel for API key management
  - Internal TTS API  (POST /api/tts)
  - OpenAI-compatible TTS API (POST /v1/audio/speech, GET /v1/models)
  - API key management: add / delete / rename / set quota / view usage
  - Per-key quota tracking (unlimited or fixed call count)
  - Model registered as "hojo-tts-light-40m"
  - Default OpenAI voice: hojo_zh_f_02 (中文女声2)
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import uuid
import hmac
import hashlib
import secrets
import threading
import platform
from datetime import datetime
from pathlib import Path
from functools import wraps
from collections import deque

import numpy as np
from flask import Flask, render_template, request, jsonify, send_file, Response, send_from_directory, abort

# Fixed random seed for reproducibility.
# NOTE: The ONNX inference engine (onnx_model.py) uses a per-thread RNG
# (np.random.default_rng(42)) internally, so concurrent inference is
# lock-free AND deterministic. This global seed only protects other code
# paths that may use the shared np.random state.
np.random.seed(42)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODELS_DIR = PROJECT_ROOT / "models"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = PROJECT_ROOT / "config.json"
API_SECRET_PATH = PROJECT_ROOT / ".api_secret"

# ---------------------------------------------------------------------------
# Internal API hash (站内API哈希) — generated at startup, stored locally.
# The operator sends this hash to requesters; every /api/tts call must carry
# a timestamped HMAC signature proving knowledge of the hash.
# ---------------------------------------------------------------------------
INTERNAL_SIG_TTL = 300          # seconds; requests older than this are rejected
_NONCE_MAX = 4096               # max remembered nonces (replay protection)


def _load_or_create_api_hash() -> str:
    """Load existing .api_secret or generate a new one (mode 0600)."""
    try:
        if API_SECRET_PATH.exists():
            val = API_SECRET_PATH.read_text(encoding="utf-8").strip()
            if val:
                return val
        val = secrets.token_hex(32)
        API_SECRET_PATH.write_text(val + "\n", encoding="utf-8")
        try:
            os.chmod(API_SECRET_PATH, 0o600)
        except OSError:
            pass
        print(f"[Auth] Generated new internal API hash file: {API_SECRET_PATH}")
        return val
    except Exception as exc:
        print(f"[Auth] Warning: cannot persist API hash: {exc}", file=sys.stderr)
        return secrets.token_hex(32)


API_HASH = _load_or_create_api_hash()
_used_nonces: deque = deque(maxlen=_NONCE_MAX * 4)
_nonce_seen: set[str] = set()
_nonce_lock = threading.Lock()


def _is_nonce_reused(nonce: str) -> bool:
    """Replay protection: reject a nonce seen within the TTL window."""
    if not nonce:
        return True
    with _nonce_lock:
        if nonce in _nonce_seen:
            return True
        _nonce_seen.add(nonce)
        _used_nonces.append(nonce)
        while len(_nonce_seen) > _NONCE_MAX:
            _nonce_seen.pop()
    return False


def _compute_internal_sig(secret: str, ts: int, nonce: str, body_sha256: str) -> str:
    msg = f"{ts}:{nonce}:{body_sha256}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def _verify_internal_request() -> tuple[bool, str]:
    """Verify X-Timestamp / X-Nonce / X-Hash headers for /api/tts."""
    try:
        ts = int(request.headers.get("X-Timestamp", ""))
    except (TypeError, ValueError):
        return False, "Missing or invalid X-Timestamp header."
    nonce = (request.headers.get("X-Nonce") or "").strip()
    sig = (request.headers.get("X-Hash") or "").strip()
    if not nonce or not sig:
        return False, "Missing X-Nonce or X-Hash header."
    now = int(time.time())
    if abs(now - ts) > INTERNAL_SIG_TTL:
        return False, "Request timestamp expired or too far in the future."
    if _is_nonce_reused(nonce):
        return False, "Nonce has already been used (replay attempt)."
    body = request.get_data()
    body_sha = hashlib.sha256(body).hexdigest()
    expected = _compute_internal_sig(API_HASH, ts, nonce, body_sha)
    if not hmac.compare_digest(expected, sig):
        return False, "Invalid X-Hash signature."
    return True, ""

from infer import get_model  # noqa: E402

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
def detect_platform() -> tuple[str, int]:
    machine = platform.machine().lower()
    is_termux = (
        os.environ.get("TERMUX_VERSION") is not None
        or "/data/data/com.termux" in sys.prefix
        or os.path.exists("/data/data/com.termux/files/usr")
    )
    cpu = os.cpu_count() or 2
    if is_termux:
        return "ARM (Termux/mobile)", max(1, cpu - 1)
    elif machine.startswith(("aarch64", "armv8", "armv7")):
        return f"ARM Linux ({machine})", max(1, cpu // 2)
    else:
        return f"x86/desktop ({machine})", cpu


PLATFORM_LABEL, DEFAULT_THREADS = detect_platform()

# ---------------------------------------------------------------------------
# Config Manager (thread-safe, supports key quota)
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "model_name": "hojo-tts-light-40m",
    "default_voice": "hojo_zh_f_02",
    "admin_password": "",
    "api_keys": [],
    "billing_mode": "per_call",
    "openai_voice_map": {
        "alloy": "hojo_en_m_02",
        "echo": "hojo_en_m_01",
        "fable": "hojo_en_f_01",
        "onyx": "hojo_en_m_03",
        "nova": "hojo_en_f_02",
        "shimmer": "hojo_en_f_03",
    },
}

_config_lock = threading.Lock()


def _normalize_key_entry(entry) -> dict:
    """Convert a string key or partial dict to full key entry dict."""
    if isinstance(entry, str):
        return {
            "key": entry,
            "name": entry[:12] + "..." if len(entry) > 12 else entry,
            "quota": -1,
            "used": 0,
            "token_quota": -1,
            "tokens_used": 0,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    if isinstance(entry, dict):
        return {
            "key": str(entry.get("key", "")),
            "name": str(entry.get("name", entry.get("key", "")[:12])),
            "quota": int(entry.get("quota", -1)),
            "used": int(entry.get("used", 0)),
            "token_quota": int(entry.get("token_quota", -1)),
            "tokens_used": int(entry.get("tokens_used", 0)),
            "created_at": str(entry.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
        }
    return {}


def load_config() -> dict:
    """Load config.json, migrate legacy string-array keys to object array."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            merged = {**DEFAULT_CONFIG, **cfg}
            # Migrate legacy string array to object array
            raw_keys = merged.get("api_keys", [])
            if raw_keys and isinstance(raw_keys[0], str):
                merged["api_keys"] = [_normalize_key_entry(k) for k in raw_keys]
                save_config(merged)
                print("[Config] Migrated legacy string api_keys to object array.")
            return merged
        except Exception as exc:
            print(f"[Config] Warning: failed to parse config.json: {exc}, using defaults", file=sys.stderr)
            return dict(DEFAULT_CONFIG)
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        print(f"[Config] Created default config: {CONFIG_PATH}")
        return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    """Atomically save config to disk."""
    tmp_path = CONFIG_PATH.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    tmp_path.replace(CONFIG_PATH)


def get_key_entry(key: str) -> dict | None:
    """Find a key entry by key string."""
    with _config_lock:
        for entry in CONFIG.get("api_keys", []):
            if entry.get("key") == key:
                return dict(entry)
    return None


def check_and_consume_quota(key: str) -> tuple[bool, str]:
    """Check if key has call quota remaining and consume one call. Returns (allowed, reason)."""
    with _config_lock:
        for entry in CONFIG.get("api_keys", []):
            if entry.get("key") == key:
                quota = entry.get("quota", -1)
                if quota == -1:
                    entry["used"] = entry.get("used", 0) + 1
                    save_config(CONFIG)
                    return True, ""
                remaining = quota - entry.get("used", 0)
                if remaining <= 0:
                    return False, f"Quota exceeded. Used {entry.get('used', 0)}/{quota} calls."
                entry["used"] = entry.get("used", 0) + 1
                save_config(CONFIG)
                return True, ""
    return False, "Invalid API key."


def check_and_consume_token_quota(key: str, token_count: int) -> tuple[bool, str]:
    """Check if key has token quota remaining and consume tokens. Returns (allowed, reason)."""
    TOKEN_EXHAUSTED_MSG = "文本转语音模型额度已用完 请进行续费或者购买Pro版 或者联系你的模型提供商"
    with _config_lock:
        for entry in CONFIG.get("api_keys", []):
            if entry.get("key") == key:
                token_quota = entry.get("token_quota", -1)
                if token_quota == -1:
                    entry["tokens_used"] = entry.get("tokens_used", 0) + token_count
                    save_config(CONFIG)
                    return True, ""
                remaining = token_quota - entry.get("tokens_used", 0)
                if remaining < token_count:
                    return False, TOKEN_EXHAUSTED_MSG
                entry["tokens_used"] = entry.get("tokens_used", 0) + token_count
                save_config(CONFIG)
                return True, ""
    return False, "Invalid API key."


def rollback_quota(key: str) -> None:
    """Roll back one consumed per-call unit if synthesis failed after deduction."""
    with _config_lock:
        for entry in CONFIG.get("api_keys", []):
            if entry.get("key") == key and entry.get("used", 0) > 0:
                entry["used"] = entry["used"] - 1
                save_config(CONFIG)
                print(f"[Billing] Rolled back 1 call for key {_mask_key(key)}")
                return


def rollback_token_quota(key: str, token_count: int) -> None:
    """Roll back consumed tokens if synthesis failed after deduction."""
    if token_count <= 0:
        return
    with _config_lock:
        for entry in CONFIG.get("api_keys", []):
            if entry.get("key") == key and entry.get("tokens_used", 0) >= token_count:
                entry["tokens_used"] = entry["tokens_used"] - token_count
                save_config(CONFIG)
                print(f"[Billing] Rolled back {token_count} tokens for key {_mask_key(key)}")
                return


def get_api_key_from_request() -> str | None:
    """Extract Bearer API key from request headers."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return None


def generate_api_key() -> str:
    """Generate a random sk- prefixed API key."""
    return "sk-" + secrets.token_hex(24)


# ---------------------------------------------------------------------------
# Load config at startup
# ---------------------------------------------------------------------------
CONFIG = load_config()
MODEL_NAME = CONFIG.get("model_name", "hojo-tts-light-40m")
DEFAULT_VOICE = CONFIG.get("default_voice", "hojo_zh_f_02")
ADMIN_PASSWORD = CONFIG.get("admin_password", "")
OPENAI_VOICE_MAP = CONFIG.get("openai_voice_map", DEFAULT_CONFIG["openai_voice_map"])

# Build set of valid keys for fast auth check
def _valid_keys_set() -> set[str]:
    return {e["key"] for e in CONFIG.get("api_keys", []) if e.get("key")}

API_KEYS = _valid_keys_set()
AUTH_REQUIRED = len(API_KEYS) > 0
BILLING_MODE = CONFIG.get("billing_mode", "per_call")  # none | per_call | per_token

print(f"[Config] Model name: {MODEL_NAME}")
print(f"[Config] Default voice: {DEFAULT_VOICE}")
print(f"[Config] API auth required: {AUTH_REQUIRED} ({len(API_KEYS)} keys)")
print(f"[Config] Billing mode: {BILLING_MODE}")
print(f"[Config] Admin password: {'set' if ADMIN_PASSWORD else 'not set (localhost-only admin)'}")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


@app.after_request
def _security_headers(resp: Response) -> Response:
    """Add hardening headers on every response."""
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    # No inline-script CSP: the page injects window.API_HASH via a small
    # script tag served from our own origin, so keep 'self' + inline allowed.
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "media-src 'self' blob:; connect-src 'self'; object-src 'none'; "
        "base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
    )
    # Never cache pages that may embed the internal API hash.
    if request.path.startswith(("/", "/api/admin")):
        resp.headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        resp.headers.setdefault("Pragma", "no-cache")
    return resp

# Serve i18n locale files from /locales/
LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")


@app.route("/locales/<lang>.json")
def serve_locale(lang):
    if lang not in ("zh", "en"):
        abort(404)
    return send_from_directory(LOCALES_DIR, lang + ".json", mimetype="application/json")

# ---------------------------------------------------------------------------
# Model singleton
# ---------------------------------------------------------------------------
_tts = None
_tts_lock = threading.Lock()
_load_error: str | None = None


def load_model() -> None:
    global _tts, _load_error
    with _tts_lock:
        if _tts is not None or _load_error is not None:
            return
        try:
            print(f"[HojoTTS] Loading model from {MODELS_DIR} ...")
            print(f"[HojoTTS] Platform: {PLATFORM_LABEL}, threads={DEFAULT_THREADS}")
            _tts = get_model(str(MODELS_DIR))
            print(f"[HojoTTS] Model loaded. Voices: {len(_tts.available_voices)}")
        except Exception as exc:
            _load_error = str(exc)
            print(f"[HojoTTS] FAILED to load model: {exc}", file=sys.stderr)


def get_tts():
    if _load_error:
        raise RuntimeError(f"Model failed to load: {_load_error}")
    if _tts is None:
        load_model()
    if _tts is None:
        raise RuntimeError("Model is not loaded yet.")
    return _tts


# ---------------------------------------------------------------------------
# Voice metadata
# ---------------------------------------------------------------------------
VOICE_META = {
    "hojo_zh_f_01": {"lang": "中文", "sex": "女", "label": "中文女声 1"},
    "hojo_zh_f_02": {"lang": "中文", "sex": "女", "label": "中文女声 2 (默认)"},
    "hojo_en_f_01": {"lang": "English", "sex": "Female", "label": "EN Female 1"},
    "hojo_en_f_02": {"lang": "English", "sex": "Female", "label": "EN Female 2"},
    "hojo_en_f_03": {"lang": "English", "sex": "Female", "label": "EN Female 3"},
    "hojo_en_f_04": {"lang": "English", "sex": "Female", "label": "EN Female 4"},
    "hojo_en_f_05": {"lang": "English", "sex": "Female", "label": "EN Female 5"},
    "hojo_en_f_06": {"lang": "English", "sex": "Female", "label": "EN Female 6"},
    "hojo_en_f_07": {"lang": "English", "sex": "Female", "label": "EN Female 7"},
    "hojo_en_f_08": {"lang": "English", "sex": "Female", "label": "EN Female 8"},
    "hojo_en_m_01": {"lang": "English", "sex": "Male", "label": "EN Male 1"},
    "hojo_en_m_02": {"lang": "English", "sex": "Male", "label": "EN Male 2"},
    "hojo_en_m_03": {"lang": "English", "sex": "Male", "label": "EN Male 3"},
    "hojo_en_m_04": {"lang": "English", "sex": "Male", "label": "EN Male 4"},
    "hojo_en_m_05": {"lang": "English", "sex": "Male", "label": "EN Male 5"},
    "hojo_en_u_01": {"lang": "English", "sex": "Unspecified", "label": "EN Voice U1"},
}


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------
def require_api_key(f):
    """Decorator: validate Bearer token if auth is enabled. Quota checked in speech endpoint."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not AUTH_REQUIRED:
            return f(*args, **kwargs)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": {
                "message": "You didn't provide an API key. You must provide an API key in the Authorization header, e.g. 'Authorization: Bearer sk-...'.",
                "type": "invalid_request_error",
                "code": "invalid_api_key",
                "param": "Authorization"
            }}), 401
        key = auth_header[7:].strip()
        if key not in API_KEYS:
            return jsonify({"error": {
                "message": f"Incorrect API key provided: {key[:12]}... Please check that your API key is correct and has not been revoked.",
                "type": "invalid_request_error",
                "code": "invalid_api_key",
                "param": "Authorization"
            }}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Decorator: protect admin API. If admin_password set, require X-Admin-Password; else localhost only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if ADMIN_PASSWORD:
            provided = request.headers.get("X-Admin-Password", "")
            # constant-time comparison to avoid timing attacks
            if not hmac.compare_digest(provided.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8")):
                return jsonify({"error": "Invalid admin password."}), 403
        else:
            # localhost-only when no password set
            client_ip = request.remote_addr or ""
            if client_ip not in ("127.0.0.1", "::1", "localhost"):
                return jsonify({"error": "Admin API requires localhost access or admin_password set in config.json."}), 403
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------
def wav_to_buffer(wav: np.ndarray, sample_rate: int) -> io.BytesIO:
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, wav, sample_rate, format="WAV")
    buf.seek(0)
    return buf


def apply_speed(wav: np.ndarray, sample_rate: int, speed: float) -> np.ndarray:
    if abs(speed - 1.0) < 0.01:
        return wav
    target_len = int(len(wav) / speed)
    if target_len <= 0:
        return wav
    indices = np.linspace(0, len(wav) - 1, target_len)
    return np.interp(indices, np.arange(len(wav)), wav).astype(np.float32)


def resolve_voice(voice_param: str | None, tts) -> str:
    if not voice_param:
        return DEFAULT_VOICE
    voice_param = voice_param.strip()
    if voice_param in tts.available_voices:
        return voice_param
    mapped = OPENAI_VOICE_MAP.get(voice_param.lower())
    if mapped and mapped in tts.available_voices:
        return mapped
    return DEFAULT_VOICE


def _mask_key(key: str) -> str:
    """Mask API key for display: sk-abc...xyz"""
    if len(key) <= 10:
        return key[:4] + "..."
    return key[:7] + "..." + key[-4:]


# ===========================================================================
# WebUI Routes
# ===========================================================================
@app.route("/")
def index():
    # The internal API hash is injected only for localhost clients so the
    # WebUI itself can sign /api/tts requests. Remote clients must obtain the
    # hash from the admin settings page (or from the operator) and sign manually.
    client_ip = request.remote_addr or ""
    is_local = client_ip in ("127.0.0.1", "::1", "localhost")
    return render_template("index.html", api_hash=API_HASH if is_local else "", is_local=is_local)


# ===========================================================================
# Internal TTS API (站内API，无需密钥)
# ===========================================================================
@app.route("/api/voices")
def api_voices():
    try:
        tts = get_tts()
        voices = []
        for vid in sorted(tts.available_voices):
            meta = VOICE_META.get(vid, {"lang": "?", "sex": "?", "label": vid})
            voices.append({"id": vid, **meta})
        return jsonify({
            "voices": voices,
            "sample_rate": tts.sample_rate,
            "default_voice": DEFAULT_VOICE,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/tts", methods=["POST"])
def api_tts():
    # Internal API requires timestamped HMAC signature (X-Timestamp/X-Nonce/X-Hash)
    ok, err = _verify_internal_request()
    if not ok:
        return jsonify({"error": f"Internal API authentication failed: {err}"}), 401

    data = request.get_json(silent=True) or request.form
    text = (data.get("text") or "").strip()
    voice = data.get("voice") or DEFAULT_VOICE

    if not text:
        return jsonify({"error": "Text is required."}), 400
    if len(text) > 20000:
        return jsonify({"error": "Text too long (max 20000 chars)."}), 400

    try:
        tts = get_tts()
        voice = resolve_voice(voice, tts)
        wav = tts.generate(text, voice=voice)
        buf = wav_to_buffer(wav, tts.sample_rate)
        filename = f"tts_{uuid.uuid4().hex[:8]}.wav"
        return send_file(buf, mimetype="audio/wav", as_attachment=False, download_name=filename)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@app.route("/api/status")
def api_status():
    return jsonify({
        "loaded": _tts is not None,
        "load_error": _load_error,
        "platform": PLATFORM_LABEL,
        "cpu_count": os.cpu_count(),
        "default_threads": DEFAULT_THREADS,
        "voices_count": len(_tts.available_voices) if _tts else 0,
        "model_name": MODEL_NAME,
        "default_voice": DEFAULT_VOICE,
        "auth_required": AUTH_REQUIRED,
        "keys_count": len(API_KEYS),
        "billing_mode": BILLING_MODE,
        "admin_password_set": bool(ADMIN_PASSWORD),
        "openai_endpoint": "/v1/audio/speech",
        "internal_api_auth": True,
        "internal_sig_ttl": INTERNAL_SIG_TTL,
    })


@app.route("/api/admin/internal-hash", methods=["GET"])
@require_admin
def admin_internal_hash():
    """Return the internal API hash (admin only) so the operator can send it
    to requesters who need to sign /api/tts calls."""
    return jsonify({
        "internal_hash": API_HASH,
        "signature_headers": ["X-Timestamp", "X-Nonce", "X-Hash"],
        "ttl_seconds": INTERNAL_SIG_TTL,
    })


# ===========================================================================
# Admin API — API Key Management
# ===========================================================================
@app.route("/api/admin/keys", methods=["GET"])
@require_admin
def admin_list_keys():
    """List all API keys with usage stats (keys masked)."""
    with _config_lock:
        keys = []
        for entry in CONFIG.get("api_keys", []):
            quota = entry.get("quota", -1)
            used = entry.get("used", 0)
            remaining = "无限" if quota == -1 else max(0, quota - used)
            token_quota = entry.get("token_quota", -1)
            tokens_used = entry.get("tokens_used", 0)
            token_remaining = "无限" if token_quota == -1 else max(0, token_quota - tokens_used)
            keys.append({
                "key": entry.get("key", ""),
                "key_masked": _mask_key(entry.get("key", "")),
                "name": entry.get("name", ""),
                "quota": quota,
                "quota_display": "无限" if quota == -1 else str(quota),
                "used": used,
                "remaining": remaining,
                "token_quota": token_quota,
                "token_quota_display": "无限" if token_quota == -1 else str(token_quota),
                "tokens_used": tokens_used,
                "token_remaining": token_remaining,
                "created_at": entry.get("created_at", ""),
            })
    return jsonify({"keys": keys, "total": len(keys)})


@app.route("/api/admin/keys", methods=["POST"])
@require_admin
def admin_add_key():
    """Add a new API key. Body: {name, quota, token_quota, key(optional auto-generated)}."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip() or "未命名密钥"
    quota_raw = data.get("quota", -1)
    try:
        quota = int(quota_raw)
    except (ValueError, TypeError):
        quota = -1
    if quota < -1:
        quota = -1

    token_quota_raw = data.get("token_quota", -1)
    try:
        token_quota = int(token_quota_raw)
    except (ValueError, TypeError):
        token_quota = -1
    if token_quota < -1:
        token_quota = -1

    key = (data.get("key") or "").strip()
    if not key:
        key = generate_api_key()
    if len(key) < 4:
        return jsonify({"error": "API key too short (min 4 chars)."}), 400

    with _config_lock:
        # Check duplicate
        for entry in CONFIG.get("api_keys", []):
            if entry.get("key") == key:
                return jsonify({"error": "API key already exists."}), 409
        new_entry = {
            "key": key,
            "name": name,
            "quota": quota,
            "used": 0,
            "token_quota": token_quota,
            "tokens_used": 0,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        CONFIG.setdefault("api_keys", []).append(new_entry)
        save_config(CONFIG)
        # Update global auth state
        global API_KEYS, AUTH_REQUIRED
        API_KEYS = _valid_keys_set()
        AUTH_REQUIRED = len(API_KEYS) > 0

    print(f"[Admin] Added API key: {_mask_key(key)} (quota={quota}, token_quota={token_quota})")
    return jsonify({
        "message": "API key added.",
        "key": key,
        "key_masked": _mask_key(key),
        "name": name,
        "quota": quota,
        "token_quota": token_quota,
    }), 201


@app.route("/api/admin/keys/<path:key>", methods=["DELETE"])
@require_admin
def admin_delete_key(key: str):
    """Delete an API key by key string."""
    with _config_lock:
        original_len = len(CONFIG.get("api_keys", []))
        CONFIG["api_keys"] = [e for e in CONFIG.get("api_keys", []) if e.get("key") != key]
        if len(CONFIG["api_keys"]) == original_len:
            return jsonify({"error": "API key not found."}), 404
        save_config(CONFIG)
        global API_KEYS, AUTH_REQUIRED
        API_KEYS = _valid_keys_set()
        AUTH_REQUIRED = len(API_KEYS) > 0
    print(f"[Admin] Deleted API key: {_mask_key(key)}")
    return jsonify({"message": "API key deleted."})


@app.route("/api/admin/keys/<path:key>", methods=["PUT"])
@require_admin
def admin_update_key(key: str):
    """Update a key's name, quota, token_quota, or reset usage. Body: {name, quota, token_quota, reset_used, reset_tokens}."""
    data = request.get_json(silent=True) or {}
    with _config_lock:
        for entry in CONFIG.get("api_keys", []):
            if entry.get("key") == key:
                if "name" in data:
                    entry["name"] = str(data["name"]).strip() or entry["name"]
                if "quota" in data:
                    try:
                        q = int(data["quota"])
                        entry["quota"] = q if q >= -1 else -1
                    except (ValueError, TypeError):
                        pass
                if "token_quota" in data:
                    try:
                        tq = int(data["token_quota"])
                        entry["token_quota"] = tq if tq >= -1 else -1
                    except (ValueError, TypeError):
                        pass
                if data.get("reset_used"):
                    entry["used"] = 0
                if data.get("reset_tokens"):
                    entry["tokens_used"] = 0
                save_config(CONFIG)
                return jsonify({
                    "message": "API key updated.",
                    "key": _mask_key(key),
                    "name": entry.get("name"),
                    "quota": entry.get("quota"),
                    "used": entry.get("used"),
                    "token_quota": entry.get("token_quota"),
                    "tokens_used": entry.get("tokens_used"),
                })
    return jsonify({"error": "API key not found."}), 404


@app.route("/api/admin/generate-key", methods=["POST"])
@require_admin
def admin_generate_key():
    """Generate a random API key string (without adding it)."""
    return jsonify({"key": generate_api_key()})


@app.route("/api/admin/billing-mode", methods=["GET"])
@require_admin
def admin_get_billing_mode():
    """Get current billing mode."""
    return jsonify({
        "billing_mode": BILLING_MODE,
        "options": ["none", "per_call", "per_token"],
        "description": {
            "none": "不启用计费，所有有效密钥无限调用",
            "per_call": "按次计费，每次成功合成扣减1次（quota字段）",
            "per_token": "按Token计费，按输入文本Token数扣减（token_quota字段）"
        }
    })


@app.route("/api/admin/billing-mode", methods=["POST"])
@require_admin
def admin_set_billing_mode():
    """Set billing mode. Body: {billing_mode: 'none'|'per_call'|'per_token'}."""
    global BILLING_MODE
    data = request.get_json(silent=True) or {}
    mode = (data.get("billing_mode") or "").strip().lower()
    if mode not in ("none", "per_call", "per_token"):
        return jsonify({"error": "Invalid billing_mode. Must be one of: none, per_call, per_token"}), 400
    with _config_lock:
        CONFIG["billing_mode"] = mode
        save_config(CONFIG)
    BILLING_MODE = mode
    print(f"[Admin] Billing mode changed to: {mode}")
    return jsonify({"message": f"Billing mode set to {mode}.", "billing_mode": mode})


# ===========================================================================
# OpenAI-Compatible API
# ===========================================================================
@app.route("/v1/models", methods=["GET"])
@require_api_key
def openai_list_models():
    return jsonify({
        "object": "list",
        "data": [{
            "id": MODEL_NAME,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "hojo-tts-local",
            "permission": [{
                "id": f"modelperm-{MODEL_NAME}",
                "object": "model_permission",
                "created": int(time.time()),
                "allow_create_engine": False,
                "allow_sampling": True,
                "allow_logprobs": False,
                "allow_search_indices": False,
                "allow_view": True,
                "allow_fine_tuning": False,
                "organization": "*",
                "group": None,
                "is_blocking": False,
            }],
            "root": MODEL_NAME,
            "parent": None,
        }],
    })


@app.route("/v1/audio/speech", methods=["POST"])
@require_api_key
def openai_create_speech():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": {"message": "Request body must be valid JSON.", "type": "invalid_request_error"}}), 400

    model = data.get("model", "")
    text = (data.get("input") or "").strip()
    voice_param = data.get("voice") or ""
    response_format = (data.get("response_format") or "wav").lower()
    speed = float(data.get("speed", 1.0))

    if not text:
        return jsonify({"error": {"message": "'input' is required and must be a non-empty string.", "type": "invalid_request_error"}}), 400
    if len(text) > 4096:
        return jsonify({"error": {"message": "'input' too long (max 4096 chars).", "type": "invalid_request_error"}}), 400
    if speed < 0.25 or speed > 4.0:
        return jsonify({"error": {"message": "'speed' must be between 0.25 and 4.0.", "type": "invalid_request_error"}}), 400

    # Get API key for quota tracking (if auth enabled)
    api_key = get_api_key_from_request() if AUTH_REQUIRED else None
    # Tracks a deduction that must be rolled back if synthesis fails.
    deduction = None  # ("per_call", key) | ("per_token", key, count)

    try:
        tts = get_tts()
        voice = resolve_voice(voice_param, tts)

        # --- Calculate token count (needed for per_token billing and logging) ---
        from onnx_model import build_speaker_prompt
        prompt = build_speaker_prompt(text)
        token_count = int(tts.tokenizer(prompt, add_special_tokens=True, return_tensors="np")["input_ids"].shape[1])

        # --- Check & consume quota based on billing_mode ---
        if api_key and BILLING_MODE != "none":
            if BILLING_MODE == "per_call":
                allowed, reason = check_and_consume_quota(api_key)
                if not allowed:
                    entry = get_key_entry(api_key) or {}
                    used = entry.get("used", 0)
                    quota = entry.get("quota", -1)
                    return jsonify({"error": {
                        "message": f"You have exceeded your API call quota. Used {used}/{quota if quota != -1 else 'unlimited'} calls. Please upgrade your plan or contact your API provider to increase your quota.",
                        "type": "insufficient_quota",
                        "code": "insufficient_quota",
                        "quota_type": "per_call",
                        "used": used,
                        "quota": quota
                    }}), 429
                deduction = ("per_call", api_key)
            elif BILLING_MODE == "per_token":
                allowed, reason = check_and_consume_token_quota(api_key, token_count)
                if not allowed:
                    entry = get_key_entry(api_key) or {}
                    tokens_used = entry.get("tokens_used", 0)
                    token_quota = entry.get("token_quota", -1)
                    return jsonify({"error": {
                        "message": "文本转语音模型额度已用完 请进行续费或者购买Pro版 或者联系你的模型提供商",
                        "type": "insufficient_quota",
                        "code": "insufficient_quota",
                        "quota_type": "per_token",
                        "tokens_used": tokens_used,
                        "token_quota": token_quota,
                        "requested_tokens": token_count
                    }}), 429
                deduction = ("per_token", api_key, token_count)

        # --- Generate audio ---
        wav = tts.generate(text, voice=voice)
        wav = apply_speed(wav, tts.sample_rate, speed)
        duration = len(wav) / tts.sample_rate

        if response_format == "wav" or response_format == "pcm":
            buf = wav_to_buffer(wav, tts.sample_rate)
            mime, ext = "audio/wav", "wav"
        elif response_format == "mp3":
            try:
                from pydub import AudioSegment
                wav_buf = wav_to_buffer(wav, tts.sample_rate)
                audio = AudioSegment.from_wav(wav_buf)
                buf = io.BytesIO()
                audio.export(buf, format="mp3", bitrate="128k")
                buf.seek(0)
                mime, ext = "audio/mpeg", "mp3"
            except ImportError:
                buf = wav_to_buffer(wav, tts.sample_rate)
                mime, ext = "audio/wav", "wav"
        else:
            buf = wav_to_buffer(wav, tts.sample_rate)
            mime, ext = "audio/wav", "wav"

        # Success: the deduction stands (nothing to roll back).
        deduction = None
        filename = f"speech_{uuid.uuid4().hex[:8]}.{ext}"
        quota_info = f", tokens={token_count}" if api_key else ""
        print(f"[OpenAI TTS] model={MODEL_NAME} voice={voice} speed={speed} fmt={ext} duration={duration:.1f}s{quota_info}")
        return send_file(buf, mimetype=mime, as_attachment=False, download_name=filename)
    except Exception as exc:
        # Synthesis failed AFTER quota was deducted -> roll the deduction back
        # so a failed request never burns the caller's quota.
        if deduction is not None:
            try:
                if deduction[0] == "per_call":
                    rollback_quota(deduction[1])
                elif deduction[0] == "per_token":
                    rollback_token_quota(deduction[1], deduction[2])
            except Exception as rb_exc:
                print(f"[Billing] Rollback failed: {rb_exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return jsonify({"error": {"message": str(exc), "type": "internal_server_error"}}), 500


@app.route("/v1/", methods=["GET"])
@require_api_key
def openai_root():
    return jsonify({
        "message": "Hojo-TTS OpenAI-compatible API",
        "endpoints": {"models": "GET /v1/models", "speech": "POST /v1/audio/speech"},
        "model": MODEL_NAME,
        "default_voice": DEFAULT_VOICE,
    })


# ===========================================================================
# Entry point
# ===========================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hojo-TTS-Light-40M WebUI + OpenAI API + Key Management")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7860, help="Bind port (default: 7860)")
    parser.add_argument("--no-preload", action="store_true", help="Don't load model until first request")
    parser.add_argument("--debug", action="store_true", help="Flask debug mode")
    args = parser.parse_args()

    if not args.no_preload:
        load_model()

    print(f"\n{'='*60}")
    print(f"  Hojo-TTS-Light-40M  WebUI + OpenAI API + 密钥管理")
    print(f"{'='*60}")
    print(f"  WebUI:     http://127.0.0.1:{args.port}")
    print(f"  站内API:   POST http://127.0.0.1:{args.port}/api/tts  (需哈希签名)")
    print(f"  OpenAIAPI: POST http://127.0.0.1:{args.port}/v1/audio/speech")
    print(f"  模型列表:  GET  http://127.0.0.1:{args.port}/v1/models")
    print(f"  密钥管理:  WebUI 设置面板 或 /api/admin/keys")
    print(f"  模型名:    {MODEL_NAME}")
    print(f"  默认音色:  {DEFAULT_VOICE}")
    print(f"  API认证:   {'开启 (' + str(len(API_KEYS)) + '个密钥)' if AUTH_REQUIRED else '关闭'}")
    print(f"  管理密码:  {'已设置' if ADMIN_PASSWORD else '未设置 (仅本地可管理)'}")
    print(f"  平台:      {PLATFORM_LABEL}")
    print(f"  内部API哈希: {API_HASH}")
    print(f"    签名头: X-Timestamp + X-Nonce + X-Hash (HMAC-SHA256, TTL {INTERNAL_SIG_TTL}s)")
    print(f"    获取:   cat {API_SECRET_PATH.name}   或   设置页(管理员)")
    print(f"{'='*60}\n")

    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
