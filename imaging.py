"""Shared image loading and upload sanitising. Must not import insightface."""

from __future__ import annotations

import hashlib
import io
import struct
import sys
from pathlib import Path

import numpy as np
import pillow_heif
from PIL import Image, ImageCms, ImageOps

pillow_heif.register_heif_opener()

ALLOWED_EXTS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp"}
MAX_LONG_EDGE = 2048
JPEG_QUALITY = 92


class ImagingError(Exception):
    pass


def _warn_nclx(info: dict) -> None:
    """HEIF colour carried only as nclx is treated as sRGB; say so when it is not."""
    nclx = info.get("nclx_profile")
    if info.get("icc_profile") or not isinstance(nclx, dict):
        return
    primaries = nclx.get("color_primaries")
    if primaries not in (None, 1, 2):  # 1 = BT.709 (sRGB), 2 = unspecified
        print(
            f"warning: HEIF colour primaries {primaries} (nclx, no ICC profile) "
            "treated as sRGB; colours may shift",
            file=sys.stderr,
        )


def _to_8bit_gray(img: Image.Image) -> Image.Image:
    arr = np.asarray(img, dtype=np.float64)
    if arr.max(initial=0) > 255:
        arr = arr / 256.0
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "L")


def _apply_icc(img: Image.Image, icc: bytes | None) -> Image.Image:
    """Colour-convert in the image's native mode (L, RGB, CMYK) to RGB."""
    if icc and img.mode in ("L", "RGB", "CMYK"):
        try:
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            dst = ImageCms.createProfile("sRGB")
            return ImageCms.profileToProfile(img, src, dst, outputMode="RGB")
        except Exception as exc:  # noqa: BLE001 - any ICC failure falls back to no profile
            print(
                f"warning: embedded ICC profile unusable ({exc}); converting without it",
                file=sys.stderr,
            )
    return img.convert("RGB")


def load_rgb(source: Path | bytes) -> Image.Image:
    """Open, apply EXIF orientation, convert to sRGB using the embedded ICC
    profile, and return a plain RGB image with no metadata attached.

    HEIF nclx-only colour info is treated as sRGB (with a warning if it is not)."""
    try:
        fp = io.BytesIO(source) if isinstance(source, bytes) else str(source)
        img = Image.open(fp)
        img.load()
    except Exception as exc:  # unreadable or unsupported file
        raise ImagingError(f"cannot read image: {exc}") from exc
    info = dict(img.info)
    _warn_nclx(info)
    img = ImageOps.exif_transpose(img)
    icc = info.get("icc_profile")
    if img.mode.startswith("I"):  # 16-bit or 32-bit greyscale
        img = _to_8bit_gray(img)
    if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
        alpha = img.convert("RGBA").getchannel("A")
        color = img.getchannel(0) if img.mode == "LA" else img.convert("RGBA").convert("RGB")
        color = _apply_icc(color, icc).convert("RGBA")
        color.putalpha(alpha)
        img = Image.alpha_composite(Image.new("RGBA", color.size, (255, 255, 255, 255)), color)
        img = img.convert("RGB")
    else:
        img = _apply_icc(img, icc)
    # Rebuild from pixels so no metadata can ride along.
    clean = Image.new("RGB", img.size)
    clean.paste(img)
    return clean


def resize_long_edge(img: Image.Image, limit: int = MAX_LONG_EDGE) -> Image.Image:
    """Downscale so the long edge is at most `limit`. Never upscales."""
    long_edge = max(img.size)
    if long_edge <= limit:
        return img
    scale = limit / long_edge
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    return img.resize(size, Image.Resampling.LANCZOS)


def to_bgr(img: Image.Image) -> np.ndarray:
    """RGB PIL image -> BGR uint8 array, the order insightface expects."""
    arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
    return np.ascontiguousarray(arr[:, :, ::-1])


def load_bgr(source: Path | bytes) -> np.ndarray:
    return to_bgr(load_rgb(source))


def jpeg_segments(data: bytes) -> list[int]:
    """Marker bytes of the header segments before the scan data."""
    if data[:2] != b"\xff\xd8":
        raise ImagingError("not a JPEG")
    markers, i = [], 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            raise ImagingError("malformed JPEG")
        marker = data[i + 1]
        markers.append(marker)
        if marker == 0xDA:  # start of scan; header done
            break
        (length,) = struct.unpack(">H", data[i + 2 : i + 4])
        i += 2 + length
    return markers


def assert_clean_jpeg(data: bytes) -> None:
    """Fail unless the JPEG carries no EXIF, XMP, ICC, IPTC, comment or thumbnail
    (all of those live in APPn/COM header segments)."""
    markers = jpeg_segments(data)
    bad = [m for m in markers if 0xE1 <= m <= 0xEF or m == 0xFE]
    if bad:
        raise ImagingError(f"metadata segments present in upload: {[hex(m) for m in bad]}")
    if len(Image.open(io.BytesIO(data)).getexif()) != 0:
        raise ImagingError("upload still has EXIF tags")


def sanitize_for_upload(source: Path | bytes) -> bytes:
    """Return JPEG bytes (sRGB, RGB, long edge <= 2048, no metadata) for upload."""
    img = resize_long_edge(load_rgb(source))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
    data = buf.getvalue()
    assert_clean_jpeg(data)
    return data


def list_photos(folder: Path) -> tuple[list[Path], list[Path]]:
    """Return (accepted, skipped) files in natural filename order,
    case-insensitive extension match."""
    import re

    def key(p: Path):
        return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]

    files = [p for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")]
    ok = sorted((p for p in files if p.suffix.lower() in ALLOWED_EXTS), key=key)
    skipped = sorted((p for p in files if p.suffix.lower() not in ALLOWED_EXTS), key=key)
    return ok, skipped


def holdout_set(folder: Path) -> str:
    """Fingerprint of the scoring photos: sha256 over the sorted "name:sha256(raw
    bytes)" lines of list_photos(folder). rank.py writes it into ranking.csv and
    generate.py compares it, so a ranking made against other photos counts as stale."""
    ok = list_photos(folder)[0] if folder.is_dir() else []
    lines = sorted(f"{p.name}:{hashlib.sha256(p.read_bytes()).hexdigest()}" for p in ok)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()
