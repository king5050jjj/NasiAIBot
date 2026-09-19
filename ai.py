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
        """Generate a short video through the public LTX ZeroGPU Space.

        This does not use the OpenAI video API. The Hugging Face Space is public,
        but its ZeroGPU quota is limited for free users.
        """
        try:
            from gradio_client import Client, handle_file
        except ImportError as exc:
            raise RuntimeError(
                "gradio_client نصب نیست. requirements.txt را بررسی و Railway را دوباره Deploy کن."
            ) from exc

        import asyncio

        space = os.getenv("FREE_VIDEO_SPACE", "Lightricks/ltx-video-distilled")
        duration = float(os.getenv("FREE_VIDEO_SECONDS", "2"))
        height = int(os.getenv("FREE_VIDEO_HEIGHT", "512"))
        width = int(os.getenv("FREE_VIDEO_WIDTH", "704"))
        negative = os.getenv(
            "FREE_VIDEO_NEGATIVE_PROMPT",
            "worst quality, inconsistent motion, blurry, jittery, distorted, deformed"
        )

        # LTX requires dimensions divisible by 32.
        height = max(256, min(1280, (height // 32) * 32))
        width = max(256, min(1280, (width // 32) * 32))
        duration = max(0.3, min(duration, 8.5))

        def _run():
            token = os.getenv("HF_TOKEN") or None
            client = Client(space, hf_token=token)

            api_name = "image_to_video" if image_path else "text_to_video"
            input_image = handle_file(image_path) if image_path else None

            # This matches the CURRENT public API of
            # Lightricks/ltx-video-distilled:
            # prompt, negative_prompt, image, video, height, width, mode,
            # duration, frames_to_use, seed, randomize_seed,
            # guidance_scale, improve_texture
            args = [
                prompt,
                negative,
                input_image,
                None,
                height,
                width,
                "image-to-video" if image_path else "text-to-video",
                duration,
                9,
                42,
                True,
                3.0,
                True,
            ]

            return client.predict(*args, api_name=api_name)

        try:
            result = await asyncio.to_thread(_run)
        except Exception as exc:
            raise RuntimeError(
                "Hugging Face/LTX در دسترس نبود یا سهمیه ZeroGPU تمام شده است. "
                f"جزئیات: {str(exc)[:1000]}"
            ) from exc

        # Current Space returns: (output_video_path, used_seed).
        video_value = result[0] if isinstance(result, (tuple, list)) and result else result

        # Gradio can return a FileData dict or a path-like value.
        if isinstance(video_value, dict):
            video_value = (
                video_value.get("path")
                or video_value.get("url")
                or video_value.get("name")
                or video_value.get("video")
            )

        # Some Gradio versions wrap FileData one level deeper.
        if isinstance(video_value, (tuple, list)) and video_value:
            video_value = video_value[0]
            if isinstance(video_value, dict):
                video_value = (
                    video_value.get("path")
                    or video_value.get("url")
                    or video_value.get("name")
                )

        if not video_value:
            raise RuntimeError(
                "Hugging Face ویدیویی برنگرداند. "
                f"پاسخ سرویس: {str(result)[:1200]}"
            )

        if isinstance(video_value, str) and video_value.startswith(("http://", "https://")):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(video_value)
                response.raise_for_status()
                return response.content

        path = Path(str(video_value))
        if not path.exists():
            raise RuntimeError(
                f"فایل ویدیوی تولیدشده در Railway پیدا نشد: {path}"
            )

        data = path.read_bytes()
        if not data:
            raise RuntimeError("فایل ویدیوی تولیدشده خالی است.")
        return data

    async def generate_animation(self, prompt: str, image_path: str | None = None) -> bytes:
        animation_prompt = f"Create a polished animated sequence. {prompt}"
        return await self.generate_video(animation_prompt, image_path=image_path)
