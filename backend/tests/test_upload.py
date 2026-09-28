"""图片上传的校验：扩展名白名单 + 文件头（魔数）+ 大小上限。

原来的实现只看扩展名，于是把脚本改名成 ``.png`` 就能传上来。
"""

import pytest

from app.core.config import settings
from app.core.uploads import sniff_image_type, validate_image_file

from tests.conftest import auth_header

# 最小的合法文件头（不用真的能被解码，这里校验的就是魔数）
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
JPG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 28
GIF_HEADER = b"GIF89a" + b"\x00" * 26
WEBP_HEADER = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 20


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (PNG_HEADER, "png"),
        (JPG_HEADER, "jpg"),
        (GIF_HEADER, "gif"),
        (WEBP_HEADER, "webp"),
        (b"#!/bin/sh\nrm -rf /\n", None),
        (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", None),
        (b"", None),
    ],
)
def test_sniff_image_type(header, expected):
    assert sniff_image_type(header[:32]) == expected


def test_jpeg_extension_is_normalized():
    assert validate_image_file("photo.jpeg", JPG_HEADER) == "jpg"


def test_rejects_content_not_matching_extension():
    """PNG 的内容却叫 .jpg —— 说明有人在拼凑，直接拒。"""
    with pytest.raises(ValueError, match="不一致"):
        validate_image_file("evil.jpg", PNG_HEADER)


def test_rejects_disguised_script():
    with pytest.raises(ValueError, match="不是有效图片"):
        validate_image_file("evil.png", b"#!/bin/sh\nrm -rf /\n")


def test_rejects_svg():
    """SVG 能内嵌脚本，不在白名单里。"""
    with pytest.raises(ValueError, match="仅支持"):
        validate_image_file("x.svg", b"<svg/>")


def _upload(client, headers, filename, content):
    return client.post(
        "/api/v1/admin/upload",
        headers=headers,
        files={"file": (filename, content, "application/octet-stream")},
    )


def test_upload_saves_valid_image(client, db, admin, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    headers = auth_header(client, "admin_test", "admin123")

    res = _upload(client, headers, "pic.png", PNG_HEADER)

    assert res.status_code == 200, res.text
    url = res.json()["url"]
    assert url.startswith("/static/products/") and url.endswith(".png")
    assert (tmp_path / "uploads" / url.rsplit("/", 1)[-1]).exists()


def test_upload_rejects_disguised_file(client, db, admin, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    headers = auth_header(client, "admin_test", "admin123")

    res = _upload(client, headers, "shell.png", b"#!/bin/sh\nrm -rf /\n")

    assert res.status_code == 400
    assert "不是有效图片" in res.json()["detail"]


def test_upload_rejects_oversized_file(client, db, admin, tmp_path, monkeypatch):
    """超过上限直接 413，并且不会再往磁盘写。"""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    headers = auth_header(client, "admin_test", "admin123")
    oversized = PNG_HEADER + b"\x00" * (settings.max_upload_size + 10)

    res = _upload(client, headers, "big.png", oversized)

    assert res.status_code == 413
    assert not (tmp_path / "uploads").exists()


def test_upload_requires_admin(client, db, user):
    headers = auth_header(client, "buyer", "user123")

    res = _upload(client, headers, "pic.png", PNG_HEADER)

    assert res.status_code == 403
