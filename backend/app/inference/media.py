from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image, UnidentifiedImageError


class MediaValidationError(ValueError):
    pass


class MediaService:
    IMAGE_TYPES = {"image/jpeg", "image/png"}
    AUDIO_TYPES = {
        "audio/wav": "audio/wav",
        "audio/x-wav": "audio/wav",
        "audio/mpeg": "audio/mpeg",
        "audio/mp3": "audio/mpeg",
    }

    def __init__(
        self,
        max_image_bytes: int = 10_485_760,
        max_audio_bytes: int = 26_214_400,
        max_image_dimension: int = 1600,
    ):
        self.max_image_bytes = max_image_bytes
        self.max_audio_bytes = max_audio_bytes
        self.max_image_dimension = max_image_dimension

    @staticmethod
    def _check_size(data: bytes, limit: int) -> None:
        if not data:
            raise MediaValidationError("Uploaded media is empty.")
        if len(data) > limit:
            raise MediaValidationError("Uploaded media exceeds the size limit.")

    @staticmethod
    def _data_url(data: bytes, mime_type: str) -> str:
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def prepare_image(self, data: bytes, mime_type: str) -> str:
        if mime_type not in self.IMAGE_TYPES:
            raise MediaValidationError("Image must be JPEG or PNG.")
        self._check_size(data, self.max_image_bytes)
        try:
            with Image.open(BytesIO(data)) as source:
                source.verify()
            with Image.open(BytesIO(data)) as source:
                source.load()
                image = source.convert("RGB")
                image.thumbnail(
                    (self.max_image_dimension, self.max_image_dimension),
                    Image.Resampling.LANCZOS,
                )
                output = BytesIO()
                image.save(output, format="JPEG", quality=85, optimize=True)
        except (
            UnidentifiedImageError,
            OSError,
            Image.DecompressionBombError,
        ) as exc:
            raise MediaValidationError("Upload is not a valid image.") from exc
        return self._data_url(output.getvalue(), "image/jpeg")

    def prepare_audio(self, data: bytes, mime_type: str) -> str:
        normalized = self.AUDIO_TYPES.get(mime_type)
        if normalized is None:
            raise MediaValidationError("Audio must be WAV or MP3.")
        self._check_size(data, self.max_audio_bytes)
        return self._data_url(data, normalized)
