from __future__ import annotations

import os
from pathlib import Path
from typing import Any

STAGING_DIR = Path("/home/conrado/testes/vault/input")


def scan_directory(directory: str = "") -> dict[str, Any]:
    target = STAGING_DIR if not directory else Path(directory)

    if not target.exists():
        return {
            "error": "directory_not_found",
            "message": f"Directory not found: {target}",
            "requested": str(directory or STAGING_DIR),
        }

    if not target.is_dir():
        return {
            "error": "not_a_directory",
            "message": "Path is not a directory",
            "requested": str(target),
        }

    files = []
    try:
        for entry in sorted(target.rglob("*")):
            if entry.is_file():
                try:
                    stat = entry.stat()
                    files.append({
                        "path": str(entry.relative_to(target) if entry.is_relative_to(target) else entry),
                        "absolute_path": str(entry),
                        "size_bytes": stat.st_size,
                        "extension": entry.suffix.lower(),
                        "name": entry.name,
                    })
                except OSError:
                    continue
    except PermissionError as e:
        return {
            "error": "permission_denied",
            "message": f"Permission denied: {e}",
            "path": str(target),
        }

    return {
        "directory": str(target),
        "file_count": len(files),
        "files": files,
    }


if __name__ == "__main__":
    import json
    result = scan_directory()
    print(json.dumps(result, indent=2, default=str))