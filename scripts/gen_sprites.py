"""
占位立绘生成器 — 用标准库生成 200×320 纯色 PNG，无需第三方依赖。

用法（在项目根目录执行）：
    python scripts/gen_sprites.py
"""
import struct
import zlib
from pathlib import Path


def _chunk(name: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(name + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)


def make_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    r, g, b = rgb
    row = b"\x00" + bytes([r, g, b] * width)
    idat = _chunk(b"IDAT", zlib.compress(row * height, level=1))
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


SPRITES: dict[str, tuple[int, int, int]] = {
    "normal": (190, 190, 195),  # 灰白
    "happy": (255, 210, 100),   # 暖黄
    "angry": (220, 80,  80),    # 红
    "shy":   (255, 175, 200),   # 粉
    "cold":  (100, 175, 220),   # 蓝
}

OUT_DIR = Path(__file__).parent.parent / "frontend" / "src" / "assets" / "sprites"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for mood, color in SPRITES.items():
        path = OUT_DIR / f"{mood}.png"
        path.write_bytes(make_png(200, 320, color))
        print(f"  wrote {path.relative_to(Path(__file__).parent.parent)}")
    print("Done.")


if __name__ == "__main__":
    main()
