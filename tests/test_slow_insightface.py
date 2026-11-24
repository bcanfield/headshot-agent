"""Opt-in: HEADSHOT_SLOW=1 uv run --extra rank pytest -m slow

Checks that our Pillow->BGR path matches cv2 on insightface's bundled sample.
Needs the buffalo_l model (downloads ~289 MB on first use). Set
HEADSHOT_INSIGHTFACE_ROOT to reuse an existing model directory."""

import os

import numpy as np
import pytest
from PIL import Image

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(os.environ.get("HEADSHOT_SLOW") != "1", reason="set HEADSHOT_SLOW=1"),
]


def test_bgr_path_matches_cv2(tmp_path):
    pytest.importorskip("insightface")
    from insightface.data import get_image

    import imaging
    import rank

    cv_img = get_image("t1")  # BGR, as cv2 reads it
    path = tmp_path / "t1.png"
    Image.fromarray(cv_img[:, :, ::-1]).save(path)

    embed = rank.InsightFaceEmbedder(root=os.environ.get("HEADSHOT_INSIGHTFACE_ROOT"))
    direct = sorted(embed(cv_img), key=lambda f: f.bbox[0])
    ours = sorted(embed(imaging.load_bgr(path)), key=lambda f: f.bbox[0])
    assert len(direct) == len(ours) > 0
    for a, b in zip(direct, ours):
        assert rank.cosine(a.embedding, b.embedding) > 0.99
    assert direct[0].embedding.shape == (512,)
    # blank image has no faces
    assert embed(np.zeros((320, 320, 3), np.uint8)) == []
