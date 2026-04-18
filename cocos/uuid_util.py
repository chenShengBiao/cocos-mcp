"""Cocos Creator UUID utilities.

Cocos Creator 3.x serializes references in scene/prefab files using a
**compressed** UUID format that is incompatible with the standard 36-char
hyphenated form. The compression algorithm:

  1. Drop the dashes (32 hex chars total).
  2. Keep the first 5 hex chars verbatim.
  3. Group the remaining 27 hex chars into 9 × 3-char chunks.
  4. Each 3-char chunk is a 12-bit value, encoded as 2 base64 chars (6 bits each).
  5. Result is 5 + 18 = 23 characters.

Base64 alphabet: A-Z, a-z, 0-9, +, /

Example:
  '5372d6f5-721e-43f6-b004-d30da1c8a9a0' -> '5372db1ch5D9rAE0w2hyKmg'
"""
from __future__ import annotations

import uuid as _uuid

BASE64_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
BASE64_VALUES = {c: i for i, c in enumerate(BASE64_CHARS)}


def new_uuid() -> str:
    """Generate a new standard UUID4 (8-4-4-4-12 lowercase hex with dashes)."""
    return str(_uuid.uuid4())


def compress_uuid(uuid: str) -> str:
    """Compress a standard UUID to Cocos Creator's 23-char short format.

    Used in scene/prefab files as the value of `__type__` for custom script
    components.
    """
    h = uuid.replace('-', '').lower()
    if len(h) != 32 or any(c not in '0123456789abcdef' for c in h):
        raise ValueError(f"invalid uuid (need 32 hex chars): {uuid!r}")
    out = h[:5]
    for i in range(5, 32, 3):
        n = int(h[i:i + 3], 16)
        out += BASE64_CHARS[(n >> 6) & 0x3f]
        out += BASE64_CHARS[n & 0x3f]
    return out


def decompress_uuid(short: str) -> str:
    """Reverse of `compress_uuid`: 23-char short -> 36-char dashed UUID."""
    if len(short) != 23:
        raise ValueError(f"invalid compressed uuid (need 23 chars): {short!r}")
    hex_out = short[:5]
    for i in range(5, 23, 2):
        try:
            hi = BASE64_VALUES[short[i]]
            lo = BASE64_VALUES[short[i + 1]]
        except KeyError as e:
            raise ValueError(f"invalid base64 char in {short!r}: {e}") from e
        n = (hi << 6) | lo
        hex_out += f"{n:03x}"
    return f"{hex_out[:8]}-{hex_out[8:12]}-{hex_out[12:16]}-{hex_out[16:20]}-{hex_out[20:]}"


# Self-test
if __name__ == "__main__":
    sample = "5372d6f5-721e-43f6-b004-d30da1c8a9a0"
    expected = "5372db1ch5D9rAE0w2hyKmg"
    got = compress_uuid(sample)
    assert got == expected, f"compress mismatch: {got} != {expected}"
    back = decompress_uuid(expected)
    assert back == sample, f"decompress mismatch: {back} != {sample}"
    print("✓ uuid round-trip OK")
