from __future__ import annotations

import numpy as np
from fastapi import HTTPException

from backend.routes.fracture_tool4 import (
    add_gaussian_noise,
    apply_fracture,
    apply_gradient_to_mask,
    fracture,
    sample_color_gradient,
)


def test_add_gaussian_noise_bounds():
    img = np.zeros((5, 5, 3), dtype=np.uint8)
    noisy = add_gaussian_noise(img, mean=0, std=10)
    assert noisy.min() >= 0
    assert noisy.max() <= 255


def test_apply_fracture_returns_same_shape():
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    overlay = np.zeros((5, 5, 4), dtype=np.uint8)
    overlay[:, :, 3] = 255
    result = apply_fracture(img.copy(), overlay, x=5, y=5, scale=1.0, noise_std=2)
    assert result.shape == img.shape


def test_apply_fracture_out_of_bounds_returns_original():
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    overlay = np.zeros((10, 10, 4), dtype=np.uint8)
    overlay[:, :, 3] = 255
    result = apply_fracture(img.copy(), overlay, x=50, y=50, scale=1.0, noise_std=1)
    assert np.array_equal(result, img)


def test_sample_color_gradient_fallbacks():
    bright = np.full((60, 60, 3), 255, dtype=np.uint8)
    mask = np.zeros((10, 10), dtype=np.uint8)
    c1, c2, direction = sample_color_gradient(bright, mask, x=0, y=0)
    assert tuple(direction) == (1, 0)
    assert c1.shape == (3,)
    assert c2.shape == (3,)

    img = np.full((60, 60, 3), 255, dtype=np.uint8)
    img[6, 5] = [0, 0, 0]
    mask_full = np.full((10, 10), 255, dtype=np.uint8)
    c1, c2, direction = sample_color_gradient(img, mask_full, x=0, y=0)
    assert direction.shape == (2,)
    assert np.all(c1 >= 0)
    assert np.all(c2 >= 0)


def test_apply_gradient_to_mask_fallback_branches():
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    # Empty overlay after clipping should early return.
    empty_overlay = np.zeros((0, 0, 4), dtype=np.uint8)
    same = apply_gradient_to_mask(
        img.copy(),
        x=0,
        y=0,
        overlay=empty_overlay,
        gradient_dir=np.array([0, 0]),
        color1=np.array([0, 0, 0], dtype=np.float32),
        color2=np.array([255, 255, 255], dtype=np.float32),
        noise_std=1,
    )
    assert np.array_equal(same, img)

    # Zero alpha forces the min/max projection fallback branch.
    overlay = np.zeros((4, 4, 4), dtype=np.uint8)
    result = apply_gradient_to_mask(
        img.copy(),
        x=1,
        y=1,
        overlay=overlay,
        gradient_dir=np.array([0, 0]),
        color1=np.array([10, 10, 10], dtype=np.float32),
        color2=np.array([20, 20, 20], dtype=np.float32),
        noise_std=1,
    )
    assert result.shape == img.shape


def test_apply_fracture_endpoint_valid(
    sample_image_bytes, sample_overlay_bytes, make_upload_file
):
    response = fracture(
        x=1,
        y=1,
        scale=1.0,
        noise=1,
        image_file=make_upload_file(sample_image_bytes, "image.png"),
        overlay_file=make_upload_file(sample_overlay_bytes, "overlay.png"),
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_apply_fracture_endpoint_invalid(make_upload_file):
    try:
        fracture(
            x=1,
            y=1,
            scale=1.0,
            noise=1,
            image_file=make_upload_file(b"not-image", "bad.txt"),
            overlay_file=make_upload_file(b"not-image", "bad.txt"),
        )
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 400
