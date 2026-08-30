#!/usr/bin/env python3
"""Generate an exact deterministic manifest for a frozen Krita ZIP artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def generate(artifact: Path) -> dict[str, object]:
    artifact_bytes = artifact.read_bytes()
    with zipfile.ZipFile(artifact) as archive:
        members = archive.infolist()
        entries = [
            {
                "compressed_size": member.compress_size,
                "compression": (
                    "stored"
                    if member.compress_type == zipfile.ZIP_STORED
                    else "deflate"
                    if member.compress_type == zipfile.ZIP_DEFLATED
                    else f"unknown:{member.compress_type}"
                ),
                "create_system": member.create_system,
                "date_time": list(member.date_time),
                "external_attr": member.external_attr,
                "kind": "directory" if member.is_dir() else "file",
                "path": member.filename,
                "sha256": sha256_bytes(archive.read(member)),
                "size": member.file_size,
            }
            for member in members
        ]
    return {
        "artifact_filename": artifact.name,
        "artifact_sha256": sha256_bytes(artifact_bytes),
        "artifact_size": len(artifact_bytes),
        "directory_entry_count": sum(
            entry["kind"] == "directory" for entry in entries
        ),
        "entries": entries,
        "entry_count": len(entries),
        "file_entry_count": sum(entry["kind"] == "file" for entry in entries),
        "schema": 2,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    manifest = generate(arguments.artifact)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
