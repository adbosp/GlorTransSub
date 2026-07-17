"""Cloud and local text-to-speech backends for GloSub."""

import asyncio
import json
import os
import tempfile
from xml.sax.saxutils import escape

import requests


REQUEST_TIMEOUT = (8, 35)

TTS_PROVIDERS = {
    "edge": {
        "label": "Microsoft Edge TTS (Free)",
        "model": "",
        "voice": "vi-VN-HoaiMyNeural",
        "fields": [],
    },
    "openai": {
        "label": "OpenAI TTS",
        "model": "gpt-4o-mini-tts",
        "models": ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"],
        "voice": "coral",
        "voices": ["coral", "alloy", "ash", "ballad", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse"],
        "fields": [("api_key", "OpenAI API Key", True)],
    },
    "elevenlabs": {
        "label": "ElevenLabs",
        "model": "eleven_multilingual_v2",
        "models": ["eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_turbo_v2_5"],
        "voice": "JBFqnCBsd6RMkjVDRZzb",
        "voices": [],
        "fields": [("api_key", "ElevenLabs API Key", True)],
    },
    "google": {
        "label": "Google Cloud TTS",
        "model": "",
        "voice": "",
        "voices": [],
        "fields": [("service_account_json", "Service Account JSON", True)],
    },
    "azure": {
        "label": "Microsoft Azure Speech",
        "model": "",
        "voice": "vi-VN-HoaiMyNeural",
        "voices": [],
        "fields": [
            ("api_key", "Azure Speech Key", True),
            ("region", "Azure Region (e.g. southeastasia)", False),
        ],
    },
    "polly": {
        "label": "Amazon Polly",
        "model": "neural",
        "models": ["neural", "standard", "generative", "long-form"],
        "voice": "Joanna",
        "voices": [],
        "fields": [
            ("access_key_id", "AWS Access Key ID", True),
            ("secret_access_key", "AWS Secret Access Key", True),
            ("session_token", "AWS Session Token (optional)", True),
            ("region", "AWS Region (e.g. us-east-1)", False),
        ],
    },
}


class TTSEngine:
    def __init__(self, provider="edge", model="", voice="", language="vi-VN", fields=None, session=None):
        if provider not in TTS_PROVIDERS:
            raise ValueError(f"Unsupported TTS provider: {provider}")
        details = TTS_PROVIDERS[provider]
        self.provider = provider
        self.model = (model or details.get("model", "")).strip()
        self.voice = (voice if voice is not None else details.get("voice", "")).strip()
        self.language = (language or "vi-VN").strip()
        self.fields = dict(fields or {})
        self.session = session or requests.Session()
        self._validate()

    @property
    def cache_key(self):
        region = self.fields.get("region", "")
        return f"{self.provider}:{self.model}:{self.voice}:{self.language}:{region}"

    def _require(self, name):
        value = (self.fields.get(name) or "").strip()
        if not value:
            label = next(
                (label for key, label, _ in TTS_PROVIDERS[self.provider]["fields"] if key == name),
                name,
            )
            raise ValueError(f"{label} is required")
        return value

    def _validate(self):
        if self.provider == "openai":
            self._require("api_key")
        elif self.provider == "elevenlabs":
            self._require("api_key")
            if not self.voice:
                raise ValueError("ElevenLabs Voice ID is required")
        elif self.provider == "google":
            raw = self._require("service_account_json")
            try:
                info = json.loads(raw)
            except Exception as exc:
                raise ValueError("Service Account JSON is invalid") from exc
            if not isinstance(info, dict) or not info.get("client_email") or not info.get("private_key"):
                raise ValueError("Service Account JSON is missing client_email/private_key")
        elif self.provider == "azure":
            self._require("api_key")
            self._require("region")
            if not self.voice:
                raise ValueError("Azure voice name is required")
        elif self.provider == "polly":
            self._require("access_key_id")
            self._require("secret_access_key")
            self._require("region")
            if not self.voice:
                raise ValueError("Amazon Polly Voice ID is required")

    @staticmethod
    def _http_error(response):
        try:
            payload = response.json()
            detail = payload.get("error", payload)
            if isinstance(detail, dict):
                detail = detail.get("message") or detail.get("status") or str(detail)
            return str(detail)[:350]
        except Exception:
            return (response.text or response.reason)[:350]

    def _post(self, url, headers=None, json_body=None, data=None):
        response = self.session.post(
            url,
            headers=headers,
            json=json_body,
            data=data,
            timeout=REQUEST_TIMEOUT,
        )
        if not response.ok:
            raise RuntimeError(f"HTTP {response.status_code}: {self._http_error(response)}")
        return response

    def synthesize_to_file(self, text, output_path):
        text = (text or "").strip()
        if not text:
            raise ValueError("Text is empty")

        if self.provider == "edge":
            import edge_tts
            asyncio.run(edge_tts.Communicate(text, self.voice).save(output_path))
            return

        if self.provider == "openai":
            payload = {
                "model": self.model,
                "voice": self.voice,
                "input": text,
                "response_format": "mp3",
            }
            if self.model == "gpt-4o-mini-tts":
                payload["instructions"] = "Speak naturally and concisely for a film or game subtitle."
            response = self._post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {self._require('api_key')}",
                    "Content-Type": "application/json",
                },
                json_body=payload,
            )
            self._write_audio(output_path, response.content)
            return

        if self.provider == "elevenlabs":
            response = self._post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice}",
                headers={"xi-api-key": self._require("api_key"), "Content-Type": "application/json"},
                json_body={"text": text, "model_id": self.model},
            )
            self._write_audio(output_path, response.content)
            return

        if self.provider == "google":
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account

            info = json.loads(self._require("service_account_json"))
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            credentials.refresh(Request())
            voice = {"languageCode": self.language}
            if self.voice:
                voice["name"] = self.voice
            response = self._post(
                "https://texttospeech.googleapis.com/v1/text:synthesize",
                headers={"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"},
                json_body={
                    "input": {"text": text},
                    "voice": voice,
                    "audioConfig": {"audioEncoding": "MP3"},
                },
            )
            try:
                import base64
                audio = base64.b64decode(response.json()["audioContent"])
            except Exception as exc:
                raise RuntimeError("Google Cloud TTS returned invalid audio") from exc
            self._write_audio(output_path, audio)
            return

        if self.provider == "azure":
            region = self._require("region")
            ssml = (
                f'<speak version="1.0" xml:lang="{escape(self.language)}">'
                f'<voice name="{escape(self.voice)}">{escape(text)}</voice></speak>'
            )
            response = self._post(
                f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
                headers={
                    "Ocp-Apim-Subscription-Key": self._require("api_key"),
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
                    "User-Agent": "GloSub",
                },
                data=ssml.encode("utf-8"),
            )
            self._write_audio(output_path, response.content)
            return

        import boto3
        client = boto3.Session(
            aws_access_key_id=self._require("access_key_id"),
            aws_secret_access_key=self._require("secret_access_key"),
            aws_session_token=(self.fields.get("session_token") or None),
            region_name=self._require("region"),
        ).client("polly")
        response = client.synthesize_speech(
            Engine=self.model,
            OutputFormat="mp3",
            Text=text,
            TextType="text",
            VoiceId=self.voice,
        )
        stream = response.get("AudioStream")
        if stream is None:
            raise RuntimeError("Amazon Polly returned no audio")
        try:
            self._write_audio(output_path, stream.read())
        finally:
            stream.close()

    @staticmethod
    def _write_audio(path, content):
        if not content:
            raise RuntimeError("TTS provider returned empty audio")
        with open(path, "wb") as handle:
            handle.write(content)


def test_tts_provider(provider, model, voice, language, fields):
    path = ""
    try:
        engine = TTSEngine(provider, model, voice, language, fields)
        fd, path = tempfile.mkstemp(prefix="glosub-tts-test-", suffix=".mp3")
        os.close(fd)
        engine.synthesize_to_file("Hello. This is a GloSub voice test.", path)
        if os.path.getsize(path) < 32:
            raise RuntimeError("TTS provider returned an invalid audio file")
        return True, "Connected successfully. Voice test audio was generated."
    except Exception as exc:
        return False, str(exc)
    finally:
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
