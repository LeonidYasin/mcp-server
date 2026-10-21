"""Prepare one MCP arguments file from local bytes; no network, tokens or shell.

An agent capable of file-backed MCP calls can pass the output as arguments_file_path.
Never print/read the chunk JSON into model text. Input files must stay unchanged.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets

CHUNK_BYTES = 48 * 1024


def prepare(source: Path, action: str, upload_id=None, offset=0):
    if action == "begin":
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as stream:
            while True:
                block = stream.read(CHUNK_BYTES)
                if not block:
                    break
                size += len(block)
                if size > 64 * 1024 * 1024:
                    raise ValueError("file_size_limit")
                digest.update(block)
        return {"name": source.name, "size": size, "sha256": digest.hexdigest(),
                "request_key": secrets.token_hex(32)}
    if action != "chunk" or offset < 0 or not isinstance(upload_id, str) or len(upload_id) != 64 or any(c not in "0123456789abcdef" for c in upload_id):
        raise ValueError("invalid_chunk_request")
    with source.open("rb") as stream:
        stream.seek(offset)
        raw = stream.read(CHUNK_BYTES)
    if not raw:
        raise ValueError("no_bytes_at_offset")
    return {"upload_id": upload_id, "offset": offset, "data": base64.b64encode(raw).decode("ascii"),
            "chunk_sha256": hashlib.sha256(raw).hexdigest()}


def write_private(path: Path, args):
    # EXCL refuses existing paths/symlinks; never overwrite an unexpected file.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(args, stream, ensure_ascii=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["begin", "chunk"])
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--upload-id")
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    payload = prepare(args.source, args.action, args.upload_id, args.offset)
    write_private(args.output, payload)
    # Only metadata is printed, never bytes/base64/capabilities/paths.
    print(json.dumps({"prepared": args.action, "argument_bytes": args.output.stat().st_size,
                      "payload_printed": False}))


if __name__ == "__main__":
    main()
