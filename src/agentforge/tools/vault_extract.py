from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

STAGING_DIR = Path("/home/conrado/testes/vault/input")

PdfTxT_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx", ".doc"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}


def extract_pdf_direct(path: Path) -> dict[str, Any]:
    text = ""
    method = ""
    
    try:
        result = subprocess.run(
            f"pdftotext -layout '{path}' -",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            text = result.stdout.strip()
            method = "pdftotext"
    except Exception:
        pass
    
    if not text:
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_base = str(Path(tmp_dir) / "page")
                subprocess.run(
                    f"pdftoppm -png -singlefile '{path}' {tmp_base}",
                    shell=True,
                    capture_output=True,
                    timeout=60,
                )
                png_file = Path(f"{tmp_base}.png")
                if png_file.exists():
                    ocr_result = subprocess.run(
                        f"tesseract '{png_file}' stdout",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    png_file.unlink()
                    if ocr_result.returncode == 0 and ocr_result.stdout.strip():
                        text = ocr_result.stdout.strip()
                        method = "tesseract_ocr"
        except Exception:
            pass

    if not text:
        return {"method": "none", "text": "", "error": "no_text_extracted"}
    
    return {"method": method, "text": text}


def _extract_from_docx(path: Path) -> dict[str, Any]:
    try:
        from docx import Document
        doc = Document(path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        if text.strip():
            return {"method": "python-docx", "text": text.strip()}
    except ImportError:
        pass
    except Exception:
        pass

    try:
        result = subprocess.run(
            f"pandoc '{path}' -t plain",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return {"method": "pandoc", "text": result.stdout.strip()}
    except FileNotFoundError:
        pass

    return {"method": "none", "text": "", "error": "no_text_extracted"}


def _extract_from_image(path: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            f"tesseract '{path}' stdout",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return {"method": "tesseract", "text": result.stdout.strip(), "ocr": True}
    except FileNotFoundError:
        pass

    return {"method": "none", "text": "", "error": "no_text_extracted", "ocr": True}


def extract_file_content(
    file_path: str,
    base_directory: str = "",
) -> dict[str, Any]:
    target_dir = STAGING_DIR if not base_directory else Path(base_directory)
    path = Path(file_path)

    if not path.is_absolute():
        path = target_dir / path

    if not path.exists():
        return {
            "error": "file_not_found",
            "message": f"Arquivo não encontrado: {path}",
            "file_path": str(path),
        }

    if not path.is_file():
        return {
            "error": "not_a_file",
            "message": "Caminho não é um arquivo",
            "file_path": str(path),
        }

    ext = path.suffix.lower()

    if ext in PdfTxT_EXTENSIONS:
        result = extract_pdf_direct(path)
    elif ext in DOCX_EXTENSIONS:
        result = _extract_from_docx(path)
    elif ext in IMAGE_EXTENSIONS:
        result = _extract_from_image(path)
    else:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            result = {"method": "raw", "text": text.strip()}
        except Exception as e:
            result = {"method": "none", "text": "", "error": str(e)}

    return {
        "file_path": str(path),
        "file_name": path.name,
        "extension": ext,
        "size_bytes": path.stat().st_size,
        **result,
    }


if __name__ == "__main__":
    import json
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else ""
    if not file_path:
        print("Usage: extract_file_content <file_path>")
        sys.exit(1)
    result = extract_file_content(file_path)
    print(json.dumps(result, indent=2, default=str))