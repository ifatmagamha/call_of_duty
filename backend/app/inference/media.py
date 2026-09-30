from __future__ import annotations

import base64
import os
import tempfile
from io import BytesIO

from PIL import Image, ImageDraw, UnidentifiedImageError


class MediaValidationError(ValueError):
    pass


class MediaTooLargeError(MediaValidationError):
    pass


class MediaService:
    IMAGE_TYPES = {"image/jpeg", "image/png"}
    AUDIO_TYPES = {
        "audio/wav": "audio/wav",
        "audio/x-wav": "audio/wav",
        "audio/mpeg": "audio/mpeg",
        "audio/mp3": "audio/mpeg",
    }

    VIDEO_TYPES = {"video/mp4"}

    def __init__(
        self,
        max_image_bytes: int = 10_485_760,
        max_audio_bytes: int = 26_214_400,
        max_image_dimension: int = 1600,
        max_video_bytes: int = 26_214_400,
        max_video_seconds: float = 30,
        video_frames: int = 6,
    ):
        self.max_image_bytes = max_image_bytes
        self.max_audio_bytes = max_audio_bytes
        self.max_image_dimension = max_image_dimension
        self.max_video_bytes = max_video_bytes
        self.max_video_seconds = max_video_seconds
        self.video_frames = video_frames

    @staticmethod
    def _check_size(data: bytes, limit: int) -> None:
        if not data:
            raise MediaValidationError("Uploaded media is empty.")
        if len(data) > limit:
            raise MediaTooLargeError("Uploaded media exceeds the size limit.")

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

    def prepare_video(self, data: bytes, mime_type: str) -> tuple[str, int, float]:
        """Sample frames into one labeled 3x2 JPEG contact sheet; media is not retained."""
        import cv2

        if mime_type not in self.VIDEO_TYPES:
            raise MediaValidationError("Video must be MP4.")
        self._check_size(data, self.max_video_bytes)
        handle, path = tempfile.mkstemp(suffix=".mp4")
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(data)
            capture = cv2.VideoCapture(path)
            try:
                if not capture.isOpened():
                    raise MediaValidationError("Upload is not a valid video.")
                fps = capture.get(cv2.CAP_PROP_FPS) or 0
                count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                if fps <= 0 or count <= 0:
                    raise MediaValidationError("Upload is not a valid video.")
                duration = count / fps
                if duration > self.max_video_seconds:
                    raise MediaValidationError(
                        f"Video exceeds {self.max_video_seconds:g} seconds."
                    )
                samples = min(self.video_frames, count)
                frames = []
                for index in range(samples):
                    position = int(index * count / samples)
                    capture.set(cv2.CAP_PROP_POS_FRAMES, position)
                    ok, frame = capture.read()
                    if ok:
                        rgb = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        frames.append((position / fps, rgb))
            finally:
                capture.release()
        finally:
            os.remove(path)
        if not frames:
            raise MediaValidationError("No frames could be decoded from the video.")
        return self._contact_sheet(frames), len(frames), round(duration, 2)

    def _contact_sheet(self, frames: list[tuple[float, Image.Image]]) -> str:
        cell_w, cell_h = 533, 400
        sheet = Image.new("RGB", (cell_w * 3, cell_h * 2), "black")
        draw = ImageDraw.Draw(sheet)
        for index, (seconds, frame) in enumerate(frames):
            frame.thumbnail((cell_w, cell_h))
            x, y = (index % 3) * cell_w, (index // 3) * cell_h
            sheet.paste(frame, (x, y))
            draw.rectangle((x, y, x + 150, y + 26), fill="black")
            draw.text((x + 6, y + 6), f"Frame {index + 1} @ {seconds:.1f}s", fill="white")
        output = BytesIO()
        sheet.save(output, format="JPEG", quality=85)
        return self._data_url(output.getvalue(), "image/jpeg")
