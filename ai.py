import base64
import os
from pathlib import Path

import httpx

from config import settings


class AIProvider:
    """Real OpenAI-backed provider used by the Telegram bot.

    The provider keeps the Telegram layer independent from the API implementation.
    All credentials come from Railway environment variables.
    """

    def __init__(self):
        self.base_url = "https://api.openai.com/v1"
        self.timeout = httpx.Timeout(180.0, connect=30.0)

    def _headers(self) -> dict[str, str]:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is missing in Railway Variables.")
        return {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

    async def _request_json(self, method: str, url: str, **kwargs):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, headers=self._headers(), **kwargs)
            if response.is_error:
                raise RuntimeError(f"OpenAI API error {response.status_code}: {response.text[:1000]}")
            return response.json()

    async def chat(self, prompt: str, context: str = "", web_search: bool = False) -> str:
        model = settings.chat_model or "gpt-5.6-luna"
        tools = [{"type": "web_search"}] if web_search else None
        payload = {
            "model": model,
            "input": [
                {"role": "developer", "content": "You are a helpful multilingual Telegram AI assistant. Answer naturally in the user's language."},
                {"role": "user", "content": prompt},
            ],
        }
        if tools:
            payload["tools"] = tools
        data = await self._request_json("POST", f"{self.base_url}/responses", json=payload)
        text = data.get("output_text")
        if text:
            return text
        # Defensive fallback for response shapes returned by older SDK/API versions.
        parts = []
        for item in data.get("output", []):
            for content in item.get("content", []) if isinstance(item, dict) else []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    parts.append(content["text"])
        return "\n".join(parts).strip() or "پاسخی از مدل دریافت نشد."

    async def analyze_image(self, image_path: str, prompt: str = "این تصویر را دقیق توضیح بده.") -> str:
        raw = Path(image_path).read_bytes()
        mime = "image/jpeg"
        suffix = Path(image_path).suffix.lower()
        if suffix == ".png":
            mime = "image/png"
        elif suffix == ".webp":
            mime = "image/webp"
        elif suffix == ".gif":
            mime = "image/gif"
        data_url = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
        model = settings.chat_model or "gpt-5.6-luna"
        payload = {
            "model": model,
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url, "detail": "high"},
                ],
            }],
        }
        data = await self._request_json("POST", f"{self.base_url}/responses", json=payload)
        return data.get("output_text") or "نتوانستم تصویر را تحلیل کنم."

    async def generate_image(self, prompt: str) -> bytes:
        model = settings.image_model or "gpt-image-1"
        payload = {
            "model": model,
            "prompt": prompt,
            "size": "1024x1024",
            "quality": "auto",
            "output_format": "png",
        }
        data = await self._request_json("POST", f"{self.base_url}/images/generations", json=payload)
        item = (data.get("data") or [{}])[0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(item["url"])
                r.raise_for_status()
                return r.content
        raise RuntimeError("Image API returned no image data.")

    async def edit_image(self, image_path: str, prompt: str) -> bytes:
        model = settings.image_model or "gpt-image-1"
        image_file = Path(image_path)
        mime = "image/png" if image_file.suffix.lower() == ".png" else "image/jpeg"
        data = {
            "model": model,
            "prompt": prompt,
            "size": "1024x1024",
            "quality": "auto",
        }
        files = {"image": (image_file.name, image_file.read_bytes(), mime)}
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/images/edits", headers=headers, data=data, files=files)
            if response.is_error:
                raise RuntimeError(f"OpenAI image edit error {response.status_code}: {response.text[:1000]}")
            payload = response.json()
        item = (payload.get("data") or [{}])[0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(item["url"])
                r.raise_for_status()
                return r.content
        raise RuntimeError("Image edit API returned no image data.")

    async def transcribe(self, audio_path: str) -> str:
        model = settings.transcription_model or "gpt-4o-mini-transcribe"
        audio_file = Path(audio_path)
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        files = {"file": (audio_file.name, audio_file.read_bytes(), "application/octet-stream")}
        data = {"model": model, "response_format": "json"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/audio/transcriptions", headers=headers, data=data, files=files)
            if response.is_error:
                raise RuntimeError(f"OpenAI transcription error {response.status_code}: {response.text[:1000]}")
            payload = response.json()
        return payload.get("text", "").strip()

    async def text_to_speech(self, text: str) -> bytes:
        model = settings.tts_model or "gpt-4o-mini-tts"
        payload = {
            "model": model,
            "voice": os.getenv("OPENAI_TTS_VOICE", "alloy"),
            "input": text[:4096],
            "response_format": "mp3",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/audio/speech", headers=self._headers(), json=payload)
            if response.is_error:
                raise RuntimeError(f"OpenAI TTS error {response.status_code}: {response.text[:1000]}")
            return response.content

    async def generate_video(self, prompt: str, image_path: str | None = None) -> bytes:
        model = settings.video_model or "sora-2"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        data = {"model": model, "prompt": prompt, "seconds": settings.video_seconds, "size": settings.video_size}
        files = None
        if image_path:
            p = Path(image_path)
            mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            files = {"input_reference": (p.name, p.read_bytes(), mime)}
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
            response = await client.post(f"{self.base_url}/videos", headers=headers, data=data, files=files)
            if response.is_error:
                raise RuntimeError(f"OpenAI video error {response.status_code}: {response.text[:1000]}")
            job = response.json()
            video_id = job["id"]
            for _ in range(settings.video_poll_attempts):
                await __import__("asyncio").sleep(settings.video_poll_seconds)
                r = await client.get(f"{self.base_url}/videos/{video_id}", headers=headers)
                if r.is_error:
                    raise RuntimeError(f"OpenAI video status error {r.status_code}: {r.text[:1000]}")
                state = r.json()
                if state.get("status") == "completed":
                    content = await client.get(f"{self.base_url}/videos/{video_id}/content", headers=headers)
                    if content.is_error:
                        raise RuntimeError(f"OpenAI video download error {content.status_code}: {content.text[:1000]}")
                    return content.content
                if state.get("status") in {"failed", "cancelled"}:
                    raise RuntimeError(f"Video generation failed: {state.get('error') or state.get('status')}")
        raise RuntimeError("Video generation timed out. Increase VIDEO_POLL_ATTEMPTS if needed.")

    async def generate_animation(self, prompt: str, image_path: str | None = None) -> bytes:
        animation_prompt = f"Create a polished animated sequence. {prompt}"
        return await self.generate_video(animation_prompt, image_path=image_path)
