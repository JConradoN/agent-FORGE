from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def read_log_tail(
    log_path: str = "./logs/app.log",
    lines: int = 50,
    filter: str = "",
) -> dict[str, Any]:
    max_size_mb = 10
    path = Path(log_path).expanduser().resolve()

    if not path.exists():
        return {
            "file_path": str(path),
            "error": "file_not_found",
            "message": f"File not found: {path}",
        }

    if not path.is_file():
        return {
            "file_path": str(path),
            "error": "not_a_file",
            "message": "Path is not a regular file",
        }

    size_bytes = path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > max_size_mb:
        return {
            "file_path": str(path),
            "error": "file_too_large",
            "message": f"File larger than {max_size_mb}MB ({size_mb:.1f}MB). Use a different file start or decrease lines.",
        }

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_content = f.readlines()
    except OSError as e:
        return {
            "file_path": str(path),
            "error": "read_error",
            "message": f"Error reading file: {e}",
        }

    total_lines = len(all_content)

    if filter:
        filtered = [line for line in all_content if filter.lower() in line.lower()]
        content = filtered[-lines:] if len(filtered) > lines else filtered
    else:
        content = all_content[-lines:]

    return {
        "file_path": str(path),
        "total_lines": total_lines,
        "returned_lines": len(content),
        "content": [line.rstrip("\n") for line in content],
        "filtered": bool(filter),
    }


if __name__ == "__main__":
    import json
    import sys

    log_path = sys.argv[1] if len(sys.argv) > 1 else "./logs/app.log"
    lines = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    result = read_log_tail(log_path, lines)
    print(json.dumps(result, indent=2, ensure_ascii=False))