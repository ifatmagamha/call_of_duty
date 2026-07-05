from io import BytesIO

import pytest
from PIL import Image

from app.inference.media import MediaValidationError, MediaService


def png_bytes(size=(20, 10)):
    stream = BytesIO()
    Image.new("RGB", size, color="red").save(stream, format="PNG")
    return stream.getvalue()


def test_image_is_validated_normalized_and_bounded():
    data_url = MediaService(max_image_bytes=100_000).prepare_image(
        png_bytes((2000, 1000)), "image/png"
    )
    assert data_url.startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize("mime", ["image/gif", "text/plain"])
def test_image_rejects_unapproved_mime(mime):
    with pytest.raises(MediaValidationError, match="JPEG or PNG"):
        MediaService().prepare_image(png_bytes(), mime)


def test_image_rejects_oversize_and_invalid_content():
    with pytest.raises(MediaValidationError, match="size limit"):
        MediaService(max_image_bytes=4).prepare_image(png_bytes(), "image/png")
    with pytest.raises(MediaValidationError, match="valid image"):
        MediaService().prepare_image(b"not an image", "image/png")


@pytest.mark.parametrize(
    ("mime", "prefix"),
    [("audio/wav", "data:audio/wav;base64,"), ("audio/mpeg", "data:audio/mpeg;base64,")],
)
def test_audio_accepts_wav_and_mp3(mime, prefix):
    assert MediaService().prepare_audio(b"audio", mime).startswith(prefix)


def test_audio_rejects_mime_and_oversize():
    with pytest.raises(MediaValidationError, match="WAV or MP3"):
        MediaService().prepare_audio(b"audio", "audio/ogg")
    with pytest.raises(MediaValidationError, match="size limit"):
        MediaService(max_audio_bytes=4).prepare_audio(b"audio", "audio/wav")
