from __future__ import annotations

import base64
import hashlib
import mimetypes
from pathlib import Path


def split_image_paths(raw_value: str) -> list[str]:
    return [part.strip() for part in raw_value.split(";") if part.strip()]


def image_id_from_path(path_like: str | Path) -> str:
    return Path(path_like).stem


def image_ids_from_raw(raw_value: str) -> list[str]:
    return [image_id_from_path(path) for path in split_image_paths(raw_value)]


SUPPORTED_API_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _magic_mime_type(path: Path) -> str | None:
    magic = path.read_bytes()[:16]
    if magic.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if magic.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if magic.startswith(b"GIF87a") or magic.startswith(b"GIF89a"):
        return "image/gif"
    if magic.startswith(b"RIFF") and magic[8:12] == b"WEBP":
        return "image/webp"
    if b"ftypavif" in magic or b"ftypavis" in magic:
        return "image/avif"
    return None


def guess_mime_type(path_like: str | Path) -> str:
    path = Path(path_like)
    return _magic_mime_type(path) or mimetypes.guess_type(str(path))[0] or "image/jpeg"


def normalize_image_for_api(path_like: str | Path) -> Path:
    """Return an API-supported image path, converting AVIF/mislabeled files to JPEG.

    Some challenge files have a `.jpg` extension but contain AVIF bytes. Several
    OpenAI-compatible vision APIs reject those even when the extension says JPG.
    This function creates a deterministic cache file next to the source under
    `.orchestrate_image_cache/` and leaves original challenge images untouched.
    """
    path = Path(path_like)
    mime = guess_mime_type(path)
    if mime in SUPPORTED_API_MIME_TYPES:
        return path

    cache_dir = path.parent / ".orchestrate_image_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    converted = cache_dir / f"{path.stem}-{digest}.jpg"
    if converted.exists():
        return converted

    try:
        import pillow_avif  # noqa: F401  # registers AVIF support with Pillow
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Unsupported image format detected and conversion dependencies are missing. "
            "Install pillow and pillow-avif-plugin."
        ) from exc

    with Image.open(path) as image:
        image = image.convert("RGB")
        image.save(converted, format="JPEG", quality=92, optimize=True)
    return converted


def image_to_data_url(path_like: str | Path) -> str:
    path = normalize_image_for_api(path_like)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{guess_mime_type(path)};base64,{encoded}"


def build_openai_compatible_image_content(
    prompt_text: str,
    image_paths: list[str | Path],
) -> list[dict[str, object]]:
    content: list[dict[str, object]] = [{"type": "text", "text": prompt_text}]
    for image_path in image_paths:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": image_to_data_url(image_path)},
            }
        )
    return content
