"""Translation backends used by GloSub."""

import os
import re
import sys
from collections import OrderedDict
from threading import Event, Lock
from urllib.parse import quote

import requests

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None


os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

MAX_CACHE_SIZE = 1024
MAX_CACHE_BYTES = 4 * 1024 * 1024
REQUEST_TIMEOUT = (8, 30)

AI_PROVIDERS = {
    "openai": {
        "label": "ChatGPT (OpenAI)",
        "model": "gpt-5.4-mini",
        "models": ["gpt-5.4-mini", "gpt-5.4-nano", "gpt-5-mini"],
        "env": "OPENAI_API_KEY",
    },
    "gemini": {
        "label": "Gemini",
        "model": "gemini-3.8-flash",
        "models": ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.5-flash"],
        "env": "GEMINI_API_KEY",
    },
    "deepseek": {
        "label": "DeepSeek",
        "model": "deepseek-flash",
        "models": ["deepseek-flash", "deepseek-v4-pro", "deepseek-v4-flash"],
        "env": "DEEPSEEK_API_KEY",
    },
    "claude": {
        "label": "Claude",
        "model": "claude-sonnet-5",
        "models": ["claude-sonnet-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
        "env": "ANTHROPIC_API_KEY",
    },
    "xai": {
        "label": "xAI (Grok)",
        "model": "grok-4.3",
        "models": ["grok-4.3", "grok-4.7"],
        "env": "XAI_API_KEY",
    },
}

GOOGLE_LANGUAGE_ALIASES = {"zh-cn": "zh-CN", "zh-tw": "zh-TW"}
LANGUAGE_NAMES = {
    "auto": "the detected source language",
    "en": "English", "vi": "Vietnamese", "ja": "Japanese",
    "ko": "Korean", "zh-cn": "Simplified Chinese",
    "zh-tw": "Traditional Chinese", "fr": "French", "de": "German",
    "es": "Spanish", "ru": "Russian", "th": "Thai",
}

_google_pool = {}
_google_lock = Lock()


def normalize_text(text):
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.strip().splitlines()]
    return "\n".join(line for line in lines if line)


class GoogleEngine:
    name = "google"

    def __init__(self):
        if not GoogleTranslator:
            raise RuntimeError("deep-translator is not installed")

    def _get(self, src, tgt):
        src = GOOGLE_LANGUAGE_ALIASES.get(src, src)
        tgt = GOOGLE_LANGUAGE_ALIASES.get(tgt, tgt)
        key = (src, tgt)
        with _google_lock:
            if key not in _google_pool:
                _google_pool[key] = GoogleTranslator(source=src, target=tgt)
            return _google_pool[key]

    def translate(self, text, src, tgt):
        return self._get(src, tgt).translate(text) or ""


class AIEngine:
    def __init__(self, provider, api_key, model=None, session=None):
        if provider not in AI_PROVIDERS:
            raise ValueError(f"Unsupported AI provider: {provider}")
        self.provider = provider
        self.api_key = (api_key or os.getenv(AI_PROVIDERS[provider]["env"], "")).strip()
        self.model = (model or AI_PROVIDERS[provider]["model"]).strip()
        self.session = session or requests.Session()
        if not self.api_key:
            raise ValueError(f"API key is required for {AI_PROVIDERS[provider]['label']}")

    @staticmethod
    def _prompt(src, tgt):
        source = LANGUAGE_NAMES.get(src, src)
        target = LANGUAGE_NAMES.get(tgt, tgt)
        return (
            "You are GloSub, an expert real-time subtitle translator. "
            f"Translate from {source} to {target}. Return only the translated text, "
            "without notes, labels, markdown, or quotation marks. Preserve line breaks, "
            "speaker names, punctuation, and placeholder tokens beginning with ZXQ exactly. "
            "Use natural, concise language suitable for films and games."
        )

    def _post(self, url, headers, payload):
        response = self.session.post(
            url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
        )
        if not response.ok:
            detail = ""
            try:
                body = response.json()
                detail = body.get("error", {}).get("message", "") if isinstance(body, dict) else ""
            except Exception:
                detail = response.text[:250]
            raise RuntimeError(f"HTTP {response.status_code}: {detail or response.reason}")
        return response.json()

    def translate(self, text, src, tgt):
        system = self._prompt(src, tgt)
        if self.provider == "openai":
            data = self._post(
                "https://api.openai.com/v1/responses",
                {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                {
                    "model": self.model,
                    "input": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": text},
                    ],
                    "max_output_tokens": 2048,
                    "store": False,
                },
            )
            result = data.get("output_text", "")
            if not result:
                result = "".join(
                    block.get("text", "")
                    for item in data.get("output", [])
                    for block in item.get("content", [])
                    if block.get("type") == "output_text"
                )
            return result.strip()

        if self.provider == "gemini":
            data = self._post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{quote(self.model, safe='')}:generateContent",
                {"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                {
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": text}]}],
                    "generationConfig": {"maxOutputTokens": 2048},
                },
            )
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini returned no candidate")
            return "".join(
                part.get("text", "")
                for part in candidates[0].get("content", {}).get("parts", [])
            ).strip()

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ]
        if self.provider == "claude":
            data = self._post(
                "https://api.anthropic.com/v1/messages",
                {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                {
                    "model": self.model,
                    "max_tokens": 2048,
                    "system": system,
                    "messages": [{"role": "user", "content": text}],
                    "thinking": {"type": "disabled"},
                },
            )
            return "".join(
                item.get("text", "") for item in data.get("content", [])
                if item.get("type") == "text"
            ).strip()

        base = "https://api.deepseek.com" if self.provider == "deepseek" else "https://api.x.ai/v1"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 2048,
            "stream": False,
        }
        if self.provider == "deepseek":
            payload["thinking"] = {"type": "disabled"}
        data = self._post(
            f"{base}/chat/completions",
            {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            payload,
        )
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("AI provider returned no translation")
        return (choices[0].get("message", {}).get("content") or "").strip()


class SmartTranslator:
    def __init__(self, engine="google", api_key="", model=""):
        self._lock = Lock()
        self._cache = OrderedDict()
        self._cache_bytes = 0
        self._revision = 0
        self._google = GoogleEngine()
        self.engine_name = "google"
        self.model = ""
        self._engine = self._google
        self.last_error = ""
        self._paused = Event()
        self.configure(engine, api_key, model)

    def pause(self):
        self._paused.set()

    def resume(self):
        self._paused.clear()

    def configure(self, engine="google", api_key="", model=""):
        with self._lock:
            if engine == "google":
                selected = self._google
                model = ""
            elif engine == "opus_mt":
                from opus_mt import OpusMTEngine
                try:
                    selected = OpusMTEngine(model)
                except Exception as exc:
                    # Stay offline even if the selected model is unavailable.
                    self._engine = None
                    self.engine_name = engine
                    self.model = model
                    self.last_error = str(exc)
                    self._clear_cache_locked()
                    raise
                model = selected.model
                if self.engine_name == engine and self.model == model and self._engine is not None:
                    selected = self._engine
            else:
                selected = AIEngine(engine, api_key, model)
                model = selected.model
            self._engine = selected
            self.engine_name = engine
            self.model = model
            self.last_error = ""
            self._clear_cache_locked()
        print(f"[Translator] Active: {engine}{' / ' + model if model else ''}")

    # Backwards-compatible name used by older settings code.
    set_engine = configure

    def _clear_cache_locked(self):
        self._cache.clear()
        self._cache_bytes = 0
        self._revision += 1

    def clear_cache(self):
        with self._lock:
            self._clear_cache_locked()

    @staticmethod
    def _entry_size(key, result):
        # Count Python string storage (including Unicode), not just characters.
        return (sys.getsizeof(key) + sum(sys.getsizeof(part) for part in key)
                + sys.getsizeof(result))

    def translate(self, text, src="auto", tgt="vi"):
        if self._paused.is_set():
            return ""
        text = normalize_text(text or "")
        if len(text) < 2:
            return ""
        key = (src, tgt, text)
        with self._lock:
            engine = self._engine
            engine_name = self.engine_name
            revision = self._revision
            configuration_error = self.last_error
            if key in self._cache:
                self._cache.move_to_end(key)
                self.last_error = ""
                return self._cache[key]
        error = ""
        try:
            if engine is None:
                raise RuntimeError(configuration_error or "No translator configured.")
            result = engine.translate(text, src, tgt)
            if not result:
                raise RuntimeError("Empty translation result")
        except Exception as exc:
            error = str(exc)
            fallback = engine_name not in ("google", "opus_mt")
            print(f"[{engine_name} ERROR] {exc}" + ("; falling back to Google" if fallback else ""))
            result = ""
            if fallback and not self._paused.is_set():
                try:
                    result = self._google.translate(text, src, tgt)
                except Exception as fallback_exc:
                    print(f"[Google fallback ERROR] {fallback_exc}")
        with self._lock:
            # Settings can change while an HTTP request is in flight. Never
            # show or cache a response from the previous configuration.
            if revision != self._revision or self._paused.is_set():
                return ""
            self.last_error = error
            if result and not error:
                size = self._entry_size(key, result)
                if size <= MAX_CACHE_BYTES:
                    previous = self._cache.pop(key, None)
                    if previous is not None:
                        self._cache_bytes -= self._entry_size(key, previous)
                    while self._cache and (
                        len(self._cache) >= MAX_CACHE_SIZE
                        or self._cache_bytes + size > MAX_CACHE_BYTES
                    ):
                        old_key, old_result = self._cache.popitem(last=False)
                        self._cache_bytes -= self._entry_size(old_key, old_result)
                    self._cache[key] = result
                    self._cache_bytes += size
            return result


def test_provider(provider, api_key, model=""):
    try:
        result = AIEngine(provider, api_key, model).translate("Hello", "en", "vi")
        if not result:
            raise RuntimeError("Empty translation result")
        return True, f"Connected successfully. Test: {result}"
    except Exception as exc:
        return False, str(exc)


def clear_translation_cache(translator=None):
    if translator is not None:
        translator.clear_cache()
    print("[CACHE] Cleared")
