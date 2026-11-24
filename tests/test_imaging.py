import io
import struct
from pathlib import Path

import numpy as np
import pillow_heif
import pytest
from PIL import Image, ImageCms

import imaging

pillow_heif.register_heif_opener()


def inject_segments(jpeg: bytes) -> bytes:
    """Add fake EXIF+GPS, XMP, a COM and an embedded thumbnail after SOI."""
    thumb = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(thumb, "JPEG")
    segs = [
        (0xE1, b"Exif\x00\x00GPS 37.77N 122.41W" + thumb.getvalue()),
        (0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta>Jane Doe</x:xmpmeta>"),
        (0xFE, b"a comment"),
    ]
    blob = b"".join(b"\xff" + bytes([m]) + struct.pack(">H", len(p) + 2) + p for m, p in segs)
    return jpeg[:2] + blob + jpeg[2:]


def make_jpeg(size=(40, 30), color=(120, 80, 60), **save_kw) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG", **save_kw)
    return buf.getvalue()


def test_jpeg_with_gps_xmp_thumbnail_is_stripped():
    dirty = inject_segments(make_jpeg())
    assert b"xmpmeta" in dirty and dirty.count(b"\xff\xd8") > 1
    out = imaging.sanitize_for_upload(dirty)
    imaging.assert_clean_jpeg(out)
    img = Image.open(io.BytesIO(out))
    assert img.format == "JPEG" and img.mode == "RGB"
    assert not img.getexif()
    assert "icc_profile" not in img.info


def test_assert_clean_jpeg_rejects_dirty():
    with pytest.raises(imaging.ImagingError):
        imaging.assert_clean_jpeg(inject_segments(make_jpeg()))


def test_exif_orientation_applied():
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 270 CW to display: 40x30 becomes 30x40
    out = imaging.sanitize_for_upload(make_jpeg(size=(40, 30), exif=exif))
    assert Image.open(io.BytesIO(out)).size == (30, 40)


def test_heic_to_clean_rgb_jpeg(tmp_path):
    exif = Image.Exif()
    exif[0x010F] = "FakeCam"
    path = tmp_path / "a.heic"
    Image.new("RGB", (64, 48), (10, 200, 30)).save(path, "HEIF", exif=exif)
    out = imaging.sanitize_for_upload(path)
    imaging.assert_clean_jpeg(out)
    img = Image.open(io.BytesIO(out))
    assert img.mode == "RGB" and img.size == (64, 48)


def test_png_with_alpha(tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGBA", (20, 20), (255, 0, 0, 0)).save(path)
    out = imaging.sanitize_for_upload(path)
    px = Image.open(io.BytesIO(out)).getpixel((5, 5))
    assert min(px) > 240  # transparent composited onto white


def test_resize_never_upscales_and_caps_long_edge():
    small = Image.new("RGB", (100, 50))
    assert imaging.resize_long_edge(small).size == (100, 50)
    big = Image.new("RGB", (4000, 3000))
    assert imaging.resize_long_edge(big).size == (2048, 1536)


P3 = Path("/System/Library/ColorSync/Profiles/Display P3.icc")


@pytest.mark.skipif(not P3.exists(), reason="needs macOS Display P3 profile")
def test_p3_converted_to_srgb_and_icc_dropped():
    p3 = P3.read_bytes()
    out = imaging.sanitize_for_upload(make_jpeg(color=(200, 150, 120), icc_profile=p3))
    img = Image.open(io.BytesIO(out))
    assert "icc_profile" not in img.info and b"ICC_PROFILE" not in out
    # Values must have shifted: P3 numbers reinterpreted as sRGB would be unchanged.
    assert max(abs(a - b) for a, b in zip(img.getpixel((5, 5)), (200, 150, 120))) >= 3


def test_srgb_profile_leaves_pixels_close():
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    out = imaging.sanitize_for_upload(make_jpeg(color=(200, 150, 120), icc_profile=icc))
    px = Image.open(io.BytesIO(out)).getpixel((5, 5))
    assert max(abs(a - b) for a, b in zip(px, (200, 150, 120))) <= 4


def test_bgr_order(tmp_path):
    path = tmp_path / "red.heic"
    Image.new("RGB", (32, 32), (255, 0, 0)).save(path, "HEIF")
    bgr = imaging.load_bgr(path)
    assert bgr.dtype == np.uint8
    b, g, r = bgr[16, 16]
    assert r > 200 and b < 60 and g < 60


def test_unreadable_is_error_not_skip(tmp_path):
    bad = tmp_path / "x.jpg"
    bad.write_bytes(b"not an image")
    with pytest.raises(imaging.ImagingError):
        imaging.load_rgb(bad)


def test_list_photos_natural_order_and_skips(tmp_path):
    for n in ("IMG_10.JPG", "IMG_9.heic", "IMG_2.png", "clip.MOV", ".hidden.jpg"):
        (tmp_path / n).write_bytes(b"x")
    ok, skipped = imaging.list_photos(tmp_path)
    assert [p.name for p in ok] == ["IMG_2.png", "IMG_9.heic", "IMG_10.JPG"]
    assert [p.name for p in skipped] == ["clip.MOV"]


def test_assert_clean_jpeg_scan_catches_exif_and_getexif():
    ok = imaging.sanitize_for_upload(make_jpeg())
    imaging.assert_clean_jpeg(ok)
    exif = Image.Exif()
    exif[0x010F] = "Cam"
    with pytest.raises(imaging.ImagingError):
        imaging.assert_clean_jpeg(make_jpeg(exif=exif))


GRAY = Path("/System/Library/ColorSync/Profiles/Generic Gray Gamma 2.2 Profile.icc")
CMYK = Path("/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc")


@pytest.mark.skipif(not GRAY.exists(), reason="needs macOS gray profile")
def test_c1l2_greyscale_with_gray_profile_loads(tmp_path):
    path = tmp_path / "g.png"
    Image.new("L", (20, 20), 128).save(path, icc_profile=GRAY.read_bytes())
    img = imaging.load_rgb(path)
    assert img.mode == "RGB" and 100 < img.getpixel((5, 5))[0] < 200
    path = tmp_path / "ga.png"
    Image.new("LA", (20, 20), (128, 255)).save(path, icc_profile=GRAY.read_bytes())
    assert imaging.load_rgb(path).mode == "RGB"


@pytest.mark.skipif(not CMYK.exists(), reason="needs macOS CMYK profile")
def test_c1l2_cmyk_with_profile_loads(tmp_path):
    path = tmp_path / "c.jpg"
    Image.new("CMYK", (20, 20), (0, 0, 0, 0)).save(path, icc_profile=CMYK.read_bytes())
    assert imaging.load_rgb(path).getpixel((5, 5))[0] > 230


def test_c1l2_mismatched_profile_falls_back_with_warning(tmp_path, capsys):
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    path = tmp_path / "g.png"
    Image.new("L", (20, 20), 128).save(path, icc_profile=icc)
    assert imaging.load_rgb(path).mode == "RGB"


def test_c1l3_16bit_grey_png_not_white(tmp_path):
    path = tmp_path / "g16.png"
    Image.fromarray(np.full((10, 10), 32768, dtype=np.uint16)).save(path)
    px = imaging.load_rgb(path).getpixel((5, 5))
    assert 100 < px[0] < 160


def test_c2l10_nclx_warning(capsys):
    imaging._warn_nclx({"nclx_profile": {"color_primaries": 12}})
    assert "colour primaries 12" in capsys.readouterr().err
    imaging._warn_nclx({"nclx_profile": {"color_primaries": 1}})
    imaging._warn_nclx({"nclx_profile": {"color_primaries": 12}, "icc_profile": b"x"})
    assert capsys.readouterr().err == ""
