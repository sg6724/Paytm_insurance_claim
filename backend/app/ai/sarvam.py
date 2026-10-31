"""Thin Sarvam client: chat (LLM), vision, speech-to-text, text-to-speech, translate.

Every call is cached on disk by input hash so sample flows replay offline.
When no key is configured, `available()` is False and callers use fallbacks.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re

import httpx

from .. import config

TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class SarvamError(Exception):
    pass


def available() -> bool:
    return bool(config.SARVAM_API_KEY)


def _headers(json_body: bool = True) -> dict:
    h = {"api-subscription-key": config.SARVAM_API_KEY}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _cache_key(task: str, payload) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return f"{task}_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


def cache_get(task: str, payload):
    p = config.AI_CACHE_DIR / f"{_cache_key(task, payload)}.json"
    if p.exists():
        return json.loads(p.read_text())
    return None


def cache_put(task: str, payload, value):
    p = config.AI_CACHE_DIR / f"{_cache_key(task, payload)}.json"
    p.write_text(json.dumps(value, ensure_ascii=False, indent=1))
    return value


def _extract_json(text: str):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def chat(messages: list[dict], *, json_mode: bool = False, max_tokens: int = 1500, temperature: float = 0.2,
         task: str = "chat", use_cache: bool = True):
    """Call Sarvam chat completions. Returns str, or parsed JSON if json_mode."""
    payload = {"messages": messages, "json": json_mode, "model": config.SARVAM_CHAT_MODEL}
    if use_cache:
        hit = cache_get(task, payload)
        if hit is not None:
            return hit["value"]
    if not available():
        raise SarvamError("Sarvam key not configured")
    body = {
        "model": config.SARVAM_CHAT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "reasoning_effort": None,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    value = None
    for attempt in range(2):
        try:
            r = httpx.post(f"{config.SARVAM_BASE}/v1/chat/completions", headers=_headers(), json=body, timeout=TIMEOUT)
            if r.status_code >= 400:
                raise SarvamError(f"chat {r.status_code}: {r.text[:300]}")
            content = r.json()["choices"][0]["message"].get("content") or ""
        except httpx.HTTPError as e:
            raise SarvamError(f"chat network error: {e}") from e
        if not json_mode:
            if content.strip() or attempt:
                value = content.strip()
                break
            # The model sometimes answers with nothing (e.g. to "let us continue"); ask once more.
            body["messages"] = messages + [{"role": "user", "content": "Please reply now in a few short sentences."}]
            continue
        try:
            value = _extract_json(content)
            break
        except (json.JSONDecodeError, ValueError):
            body["messages"] = messages + [{"role": "user", "content": "Reply again with only one valid JSON object, no other text."}]
    if value is None:
        raise SarvamError("Model did not return valid JSON")
    if use_cache:
        cache_put(task, payload, {"value": value})
    return value


def vision(prompt: str, image_bytes: bytes, mime: str = "image/jpeg", *, json_mode: bool = True, task: str = "vision"):
    """Read an image with an image-capable model on /v2/chat/completions."""
    digest = hashlib.sha256(image_bytes).hexdigest()
    payload = {"prompt": prompt, "img": digest, "model": config.SARVAM_VISION_MODEL}
    hit = cache_get(task, payload)
    if hit is not None:
        return hit["value"]
    if not available():
        raise SarvamError("Sarvam key not configured")
    b64 = base64.b64encode(image_bytes).decode()
    body = {
        "model": config.SARVAM_VISION_MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]}],
        "temperature": 0.1,
        "max_tokens": 3000,
    }
    try:
        r = httpx.post(f"{config.SARVAM_BASE}/v2/chat/completions", headers=_headers(), json=body, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise SarvamError(f"vision {r.status_code}: {r.text[:300]}")
        content = r.json()["choices"][0]["message"].get("content") or ""
    except httpx.HTTPError as e:
        raise SarvamError(f"vision network error: {e}") from e
    value = _extract_json(content) if json_mode else content.strip()
    cache_put(task, payload, {"value": value})
    return value


AUDIO_TYPES = {"m4a": "audio/x-m4a", "mp4": "audio/mp4", "aac": "audio/aac", "wav": "audio/wav", "mp3": "audio/mpeg",
               "ogg": "audio/ogg", "opus": "audio/opus", "webm": "audio/webm", "flac": "audio/flac", "amr": "audio/amr", "3gp": "audio/amr"}


def audio_type(filename: str) -> str:
    """Sarvam only accepts listed types; Python guesses audio/mp4a-latm for .m4a, which it rejects."""
    return AUDIO_TYPES.get(filename.rsplit(".", 1)[-1].lower(), "application/octet-stream")


def stt(audio: bytes, filename: str = "audio.m4a", language_code: str | None = None) -> dict:
    if not available():
        raise SarvamError("Sarvam key not configured")
    data = {"model": config.SARVAM_STT_MODEL, "mode": "transcribe"}
    if language_code and language_code != "auto":
        data["language_code"] = language_code
    try:
        r = httpx.post(f"{config.SARVAM_BASE}/speech-to-text", headers=_headers(json_body=False),
                       data=data, files={"file": (filename, audio, audio_type(filename))}, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise SarvamError(f"stt {r.status_code}: {r.text[:300]}")
        j = r.json()
    except httpx.HTTPError as e:
        raise SarvamError(f"stt network error: {e}") from e
    return {"transcript": j.get("transcript", ""), "language_code": j.get("language_code")}


def tts_voice(language_code: str) -> tuple[str, str]:
    """(model, speaker) for a language: a v4-flash persona where one exists, else the v3 fallback."""
    if config.SARVAM_TTS_MODEL.startswith("bulbul:v4"):
        speaker = config.SARVAM_TTS_SPEAKER or config.SARVAM_TTS_VOICES.get(language_code)
        if speaker:
            return config.SARVAM_TTS_MODEL, speaker
        return config.SARVAM_TTS_FALLBACK_MODEL, config.SARVAM_TTS_FALLBACK_SPEAKER
    return config.SARVAM_TTS_MODEL, config.SARVAM_TTS_SPEAKER or config.SARVAM_TTS_FALLBACK_SPEAKER


# Bulbul reads "₹" as the English "rupees" in these languages; the local word sounds natural.
RUPEE_WORD = {"ta-IN": "ரூபாய்", "te-IN": "రూపాయలు", "bn-IN": "টাকা", "ml-IN": "രൂപ"}
_RUPEE = re.compile(r"(?:₹|\bRs\.?|\bINR)\s?(\d+(?:,\d+)*(?:\.\d+)?)(\s*)(\S*)")


def speakable(text: str, language_code: str) -> str:
    word = RUPEE_WORD.get(language_code)
    if not word:
        return text
    stem = word[:3]  # matches inflected forms too (টাকার, രൂപയുടെ), so a word already there is not doubled
    return _RUPEE.sub(lambda m: f"{m[1]}{m[2]}{m[3]}" if m[3].startswith(stem) else f"{m[1]} {word}{m[2]}{m[3]}", text)


def tts(text: str, language_code: str = "hi-IN") -> dict:
    """Returns {"audio_base64": ..., "mime": "audio/wav"}."""
    text = speakable(text[:2400], language_code)
    model, speaker = tts_voice(language_code)
    v4 = model.startswith("bulbul:v4")
    payload = {"text": text, "lang": language_code, "model": model, "speaker": speaker}
    if v4:
        payload["pace"] = config.SARVAM_TTS_PACE
    hit = cache_get("tts", payload)
    if hit is not None:
        return hit.get("value", hit)  # older entries were saved unwrapped
    if not available():
        raise SarvamError("Sarvam key not configured")
    body = {"text": text, "target_language_code": language_code, "language_code": language_code,
            "model": model, "speaker": speaker}
    if v4:  # Sarvam's v4 guide: let it normalise numbers, dates and ₹ itself
        body |= {"pace": config.SARVAM_TTS_PACE, "enable_preprocessing": True}
    try:
        r = httpx.post(f"{config.SARVAM_BASE}/text-to-speech", headers=_headers(), json=body, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise SarvamError(f"tts {r.status_code}: {r.text[:300]}")
        ctype = r.headers.get("content-type", "")
        if "json" in ctype:
            j = r.json()
            audio = (j.get("audios") or [j.get("audio")])[0]
        else:
            audio = base64.b64encode(r.content).decode()
    except httpx.HTTPError as e:
        raise SarvamError(f"tts network error: {e}") from e
    value = {"audio_base64": audio, "mime": "audio/wav"}
    cache_put("tts", payload, {"value": value})
    return value


def translate(text: str, target: str, source: str = "auto") -> str:
    if target.startswith("en") or not text:
        return text
    payload = {"t": text, "to": target}
    hit = cache_get("translate", payload)
    if hit is not None:
        return hit["value"]
    if not available():
        raise SarvamError("Sarvam key not configured")
    out = chat([
        {"role": "system", "content": "You translate app text for Indian health insurance customers. Keep numbers, ₹ amounts, clause ids and dates exactly as given. Reply with the translation only."},
        {"role": "user", "content": f"Translate into {config.LANG_NAME.get(target, target)}:\n\n{text}"},
    ], task="translate_llm", max_tokens=2000)
    cache_put("translate", payload, {"value": out})
    return out
