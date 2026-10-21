"""Bounded readers for this tool's small, known-member metadata-only ZIP format."""

from __future__ import annotations

import io
import json
import math
import stat
import struct
import zipfile
import zlib
from pathlib import Path
from typing import Any

from .filesystem import chunks

MAX_BUNDLE_BYTES = 32 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MEMBERS = {"continuity.json", "HANDOFF.md", "HANDOFF.html", "VERIFY.txt"}


def validate_json(value: Any) -> None:
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if depth > 64:
            raise ValueError("JSON nesting exceeds the supported limit of 64")
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("JSON object keys must be strings")
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
        elif (
            item is None
            or type(item) in {str, bool, int}
            or isinstance(item, float)
            and math.isfinite(item)
        ):
            continue
        else:
            raise ValueError("JSON values must be finite and use JSON-compatible types")


def json_bytes(content: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON object key")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ValueError(f"Non-finite JSON number is refused: {value}")

    def finite_float(value: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Non-finite JSON number")
        return result

    try:
        result = json.loads(
            content.decode("utf-8-sig"),
            object_pairs_hook=unique,
            parse_constant=invalid_constant,
            parse_float=finite_float,
        )
        validate_json(result)
        return result
    except RecursionError as error:
        raise ValueError("JSON nesting exceeds the supported limit") from error


def _directory_guard(raw: bytes) -> tuple[int, int]:
    # Bound metadata parsing before ZipFile can allocate from untrusted EOCD fields.
    end = raw.rfind(b"PK\x05\x06")
    if end < 0 or len(raw) - end < 22:
        raise ValueError("Bundle lacks a complete ZIP end record")
    _, disk, directory_disk, count_disk, count, size, offset, comment = struct.unpack_from(
        "<4s4H2LH", raw, end
    )
    if raw[max(0, end - 20) : end - 16] == b"PK\x06\x07":
        raise ValueError("ZIP64 bundle directories are outside the bounded format")
    if disk or directory_disk or count_disk != count or not 1 <= count <= 4:
        raise ValueError("Bundle must be a single-disk ZIP with at most four members")
    if size > 512 * 1024 or offset + size != end or end + 22 + comment != len(raw):
        raise ValueError("Bundle central directory exceeds the bounded format")
    position = offset
    seen = 0
    while position < end:
        if seen >= 4 or raw[position : position + 4] != b"PK\x01\x02" or end - position < 46:
            raise ValueError("Invalid or excessive bundle directory records")
        name, extra, note = struct.unpack_from("<3H", raw, position + 28)
        position += 46 + name + extra + note
        seen += 1
    if position != end or seen != count:
        raise ValueError("Bundle directory records disagree with its end record")
    return offset, count


def _member(archive: zipfile.ZipFile, item: zipfile.ZipInfo) -> bytes:
    # Keep stdlib local-name/header/overlap checks, then validate the complete stream.
    with archive.open(item):
        source = archive.fp
        if source is None:
            raise ValueError("Bundle was closed during verification")
        source.seek(item.header_offset + 26)
        sizes = source.read(4)
        if len(sizes) != 4:
            raise ValueError("Truncated member header")
        name, extra = struct.unpack("<HH", sizes)
        source.seek(item.header_offset + 30 + name + extra)
        decoder = (
            zlib.decompressobj(-zlib.MAX_WBITS)
            if item.compress_type == zipfile.ZIP_DEFLATED
            else None
        )
        remaining = item.compress_size
        content = bytearray()
        crc = 0
        while remaining:
            block = source.read(min(65536, remaining))
            if not block:
                raise ValueError("Truncated compressed bundle member")
            remaining -= len(block)
            pending = block
            while pending:
                if decoder is None:
                    decoded, pending = pending, b""
                else:
                    try:
                        decoded = decoder.decompress(
                            pending,
                            min(65536, min(MAX_MEMBER_BYTES, item.file_size) - len(content) + 1),
                        )
                    except zlib.error as error:
                        raise ValueError("Invalid compressed bundle member") from error
                    pending = decoder.unconsumed_tail
                    if decoder.unused_data or decoder.eof and (pending or remaining):
                        raise ValueError("Trailing compressed bundle member data")
                if len(content) + len(decoded) > min(MAX_MEMBER_BYTES, item.file_size):
                    raise ValueError("Bundle member exceeds its declared size or limit")
                content.extend(decoded)
                crc = zlib.crc32(decoded, crc)
        if decoder is not None and not decoder.eof:
            raise ValueError("Incomplete compressed bundle member")
        if len(content) != item.file_size or crc != item.CRC:
            raise ValueError("Bundle member size or CRC mismatch")
        return bytes(content)


def read_bundle(path: Path) -> dict[str, bytes]:
    raw = b"".join(chunks(path, MAX_BUNDLE_BYTES))
    directory_offset, member_count = _directory_guard(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if archive.start_dir != directory_offset or len(entries) != member_count:
            raise ValueError("Parsed ZIP directory disagrees with bounded preflight")
        names = [item.filename for item in entries]
        if len(names) != len(set(names)) or set(names) not in [MEMBERS, MEMBERS - {"HANDOFF.html"}]:
            raise ValueError(
                "Bundle must contain only the three legacy or four current continuity files"
            )
        for item in entries:
            if (
                item.orig_filename != item.filename
                or item.flag_bits & 1
                or item.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
            ):
                raise ValueError("Unsupported bundle name, encryption or compression")
            if item.file_size > MAX_MEMBER_BYTES or item.compress_size > MAX_BUNDLE_BYTES:
                raise ValueError("Bundle member exceeds its size limit")
            if (
                stat.S_IFMT(item.external_attr >> 16) not in {0, stat.S_IFREG}
                or item.external_attr & 0x400
            ):
                raise ValueError("Bundle links, reparse points and special members are refused")
        if sum(item.file_size for item in entries) > MAX_BUNDLE_BYTES:
            raise ValueError("Bundle expanded total exceeds its size limit")
        return {item.filename: _member(archive, item) for item in entries}
