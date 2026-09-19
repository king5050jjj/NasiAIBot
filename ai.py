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
        """Generate a short video through a public Hugging Face ZeroGPU Space.

        This path does not use the OpenAI video API or OPENAI_VIDEO_MODEL.
        The public Space has a free daily ZeroGPU quota; it is not unlimited.
        """
        try:
            from gradio_client import Client, handle_file
        except ImportError:
            raise RuntimeError("gradio_client is not installed. Add it to requirements.txt and redeploy Railway.")

        import asyncio
        import tempfile as _tempfile

        space = os.getenv("FREE_VIDEO_SPACE", "Lightricks/ltx-video-distilled")
        duration = float(os.getenv("FREE_VIDEO_SECONDS", "2"))
        # Keep the free ZeroGPU generation lightweight.
        height = int(os.getenv("FREE_VIDEO_HEIGHT", "512"))
        width = int(os.getenv("FREE_VIDEO_WIDTH", "704"))
        negative = os.getenv(
            "FREE_VIDEO_NEGATIVE_PROMPT",
            "worst quality, inconsistent motion, blurry, jittery, distorted"
        )

        if height % 32:
            height = (height // 32) * 32
        if width % 32:
            width = (width // 32) * 32
        duration = max(0.3, min(duration, 8.5))

        def _run():
            client = Client(space)
            mode = "image-to-video" if image_path else "text-to-video"
            input_image = handle_file(image_path) if image_path else None

            # This is the public API exposed by Lightricks/ltx-video-distilled.
            result = client.predict(
                prompt,
                negative,
                input_image,
                None,
                height,
                width,
                mode,
                duration,
                9,
                42,
                True,
                3.0,
                True,
                api_name="/image_to_video" if image_path else "/text_to_video",
            )
            return result

        try:
            result = await asyncio.to_thread(_run)
        except Exception as exc:
            raise RuntimeError(
                "رایگان‌ساز ویدیو در Hugging Face در دسترس نبود یا سهمیه‌اش تمام شده است: "
                f"{exc}"
            ) from exc

        # The Space returns (video_path, seed).
        video_value = result[0] if isinstance(result, (tuple, list)) else result

        # Gradio may return a plain path/URL or a FileData-like dictionary.
        if isinstance(video_value, dict):
            video_value = (
                video_value.get("path")
                or video_value.get("url")
                or video_value.get("name")
            )

        if not video_value:
            raise RuntimeError("Hugging Face returned no video file.")

        if isinstance(video_value, str) and video_value.startswith(("http://", "https://")):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(video_value)
                r.raise_for_status()
                return r.content

        path = Path(str(video_value))
        if not path.exists():
            raise RuntimeError(f"Generated video file was not found: {path}")

        return path.read_bytes()

    async def generate_animation(self, prompt: str, image_path: str | None = None) -> bytes:
        animation_prompt = f"Create a polished animated sequence. {prompt}"
        return await self.generate_video(animation_prompt, image_path=image_path)
