"""Tests for cocos.uuid_util."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocos.uuid_util import compress_uuid, decompress_uuid, new_uuid


def test_compress_known():
    assert compress_uuid("5372d6f5-721e-43f6-b004-d30da1c8a9a0") == "5372db1ch5D9rAE0w2hyKmg"


def test_decompress_known():
    assert decompress_uuid("5372db1ch5D9rAE0w2hyKmg") == "5372d6f5-721e-43f6-b004-d30da1c8a9a0"


def test_roundtrip():
    for _ in range(20):
        u = new_uuid()
        short = compress_uuid(u)
        assert len(short) == 23
        back = decompress_uuid(short)
        assert back == u


def test_new_uuid_format():
    u = new_uuid()
    assert len(u) == 36
    parts = u.split("-")
    assert [len(p) for p in parts] == [8, 4, 4, 4, 12]


def test_compress_bad_input():
    import pytest
    with pytest.raises(ValueError):
        compress_uuid("too-short")
    with pytest.raises(ValueError):
        compress_uuid("zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz")
