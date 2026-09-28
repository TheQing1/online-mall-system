"""上传文件的类型校验。

只校验扩展名是不够的：把脚本改名成 ``.png`` 一样能传上来。这里按**文件头
（魔数）**判断真实类型，并要求它与扩展名一致。

边界写清楚：魔数只能证明「开头像图片」，挡不住精心构造的多格式文件
（polyglot）。真要彻底就该用图像库解码后重新编码再落盘，或者交给对象存储的
图片处理服务。本项目是「扩展名白名单 + 魔数校验 + 大小上限」这一档，
足以挡住「改个后缀就想传任意文件」，但不假装它是完整的图片安全方案。
"""

from typing import Optional

ALLOWED_EXTENSIONS = ("jpg", "png", "gif", "webp")

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def sniff_image_type(header: bytes) -> Optional[str]:
    """按文件头判断图片类型，返回 ``jpg`` / ``png`` / ``gif`` / ``webp`` 或 None。"""
    if header.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if header.startswith(_PNG_SIGNATURE):
        return "png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    # WebP 是 RIFF 容器：前 4 字节 RIFF，第 8-12 字节才是 WEBP
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def normalize_extension(filename: str) -> str:
    """取出扩展名并归一化（``jpeg`` → ``jpg``）；不支持时返回空串。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return "jpg" if ext == "jpeg" else ext


def validate_image_file(filename: str, content: bytes) -> str:
    """校验通过返回规范化的扩展名；不合法抛 ``ValueError``（调用方转 400）。"""
    ext = normalize_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("仅支持 jpg/png/gif/webp 格式")

    real_type = sniff_image_type(content[:32])
    if real_type is None:
        raise ValueError("文件内容不是有效图片（扩展名与实际内容不符）")
    if real_type != ext:
        raise ValueError(f"文件内容看起来是 {real_type}，与扩展名 .{ext} 不一致")
    return ext
