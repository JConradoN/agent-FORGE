#!/usr/bin/env bash
set -euo pipefail

# Raiz do repo (ajuste se precisar)
REPO_ROOT="${REPO_ROOT:-$HOME/repos/estudo/agents-framework}"

AGENT_DIR="$REPO_ROOT/agents/vault-pilot"
TOOLS_FILE="$AGENT_DIR/tools.py"

mkdir -p "$AGENT_DIR"

echo "Criando tools em: $TOOLS_FILE"

cat > "$TOOLS_FILE" << 'EOF'
"""
Tools do agente vault-pilot.

Este módulo define as funções que serão expostas como tools no AgentForge:
- scan_directory
- extract_file_content

A ideia é manter a lógica de IO/SO aqui e deixar o LLM apenas orquestrar.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple


# Diretório padrão de staging (pode ser sobreposto via input da tool)
DEFAULT_STAGING_DIR = os.path.expanduser("~/testes/vault/input")


@dataclass
class FileInfo:
    path: str
    size_bytes: int
    extension: str


def _is_under_base(path: pathlib.Path, base: pathlib.Path) -> bool:
    """
    Garante que 'path' está sob 'base', evitando escapar do staging por engano.
    """
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def scan_directory(
    base_path: Optional[str] = None,
    include_patterns: Optional[List[str]] = None,
    max_files: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Lista arquivos em um diretório de staging.

    Parâmetros:
        base_path: diretório base para varredura. Default: ~/testes/vault/input
        include_patterns: lista de padrões glob (ex.: ['*.pdf', '*.docx'])
        max_files: limite máximo de arquivos retornados (None = sem limite)

    Retorno:
        dict com:
            files: lista de { path, size_bytes, extension }
            base_path: caminho base resolvido
            total_found: número total de arquivos encontrados (antes de truncar)
    """
    base = pathlib.Path(base_path or DEFAULT_STAGING_DIR).expanduser()
    if not base.exists() or not base.is_dir():
        return {
            "files": [],
            "base_path": str(base),
            "total_found": 0,
            "error": f"base_path '{base}' não existe ou não é diretório",
        }

    patterns = include_patterns or ["*"]
    files: List[FileInfo] = []

    total_found = 0
    for root, _dirs, filenames in os.walk(base):
        root_path = pathlib.Path(root)
        for name in filenames:
            full_path = root_path / name
            if not _is_under_base(full_path, base):
                # Segurança extra.
                continue

            # Filtro por padrão simples (glob local no nome do arquivo).
            if patterns:
                matched = False
                for pat in patterns:
                    if full_path.match(pat) or pathlib.Path(name).match(pat):
                        matched = True
                        break
                if not matched:
                    continue

            try:
                stat = full_path.stat()
                files.append(
                    FileInfo(
                        path=str(full_path),
                        size_bytes=stat.st_size,
                        extension=full_path.suffix.lower(),
                    )
                )
                total_found += 1
            except OSError:
                # Ignora arquivos que não conseguimos stat-ar.
                continue

            if max_files is not None and len(files) >= max_files:
                break
        if max_files is not None and len(files) >= max_files:
            break

    return {
        "files": [fi.__dict__ for fi in files],
        "base_path": str(base),
        "total_found": total_found,
    }


def _run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    """
    Executa um comando de sistema e retorna (retcode, stdout, stderr).
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate()
    return proc.returncode, out, err


def _extract_pdf_text(path: pathlib.Path) -> Tuple[str, str, bool, List[str]]:
    """
    Tenta extrair texto de PDF.

    Estratégia:
    1. Tenta 'pdftotext' diretamente.
    2. Se vier vazio, opcionalmente poderíamos cair para OCR (pdftoppm + tesseract).

    Retorno:
        text, extract_method, ocr_used, errors
    """
    errors: List[str] = []

    # 1) pdftotext (texto nativo)
    ret, out, err = _run_cmd(["pdftotext", "-layout", str(path), "-"])
    if ret == 0 and out.strip():
        return out, "pdftotext", False, errors

    errors.append(f"pdftotext falhou ou retornou vazio: rc={ret}, err={err.strip()[:300]}")

    # Placeholder opcional para OCR no futuro; por ora, só registra erro.
    # Você pode plugar aqui pdftoppm + tesseract se quiser na v1.5.
    return "", "pdf_unknown", False, errors


def _extract_doc_text(path: pathlib.Path) -> Tuple[str, str, bool, List[str]]:
    """
    Extrai texto de arquivos DOC via 'antiword', se disponível.
    """
    errors: List[str] = []
    ret, out, err = _run_cmd(["antiword", str(path)])
    if ret == 0 and out.strip():
        return out, "antiword", False, errors

    errors.append(f"antiword falhou ou retornou vazio: rc={ret}, err={err.strip()[:300]}")
    return "", "doc_unknown", False, errors


def _extract_docx_text(path: pathlib.Path) -> Tuple[str, str, bool, List[str]]:
    """
    Extrai texto de arquivos DOCX via 'pandoc', se disponível.
    """
    errors: List[str] = []
    ret, out, err = _run_cmd(["pandoc", "-t", "plain", str(path)])
    if ret == 0 and out.strip():
        return out, "pandoc", False, errors

    errors.append(f"pandoc falhou ou retornou vazio: rc={ret}, err={err.strip()[:300]}")
    return "", "docx_unknown", False, errors


def _extract_image_ocr(path: pathlib.Path) -> Tuple[str, str, bool, List[str]]:
    """
    Extrai texto de imagens (jpg/png/etc.) via tesseract (pytesseract não é estritamente necessário
    se você já tem o binário 'tesseract' disponível).
    """
    errors: List[str] = []
    # tesseract <input> stdout
    ret, out, err = _run_cmd(["tesseract", str(path), "stdout", "-l", "por"])
    if ret == 0 and out.strip():
        return out, "tesseract", True, errors

    errors.append(f"tesseract falhou ou retornou vazio: rc={ret}, err={err.strip()[:300]}")
    return "", "image_unknown", True, errors


def _guess_extractor(path: pathlib.Path) -> Tuple[str, str, bool, List[str]]:
    """
    Escolhe o método de extração com base na extensão.
    """
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _extract_pdf_text(path)
    if ext in {".doc"}:
        return _extract_doc_text(path)
    if ext in {".docx"}:
        return _extract_docx_text(path)
    if ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
        return _extract_image_ocr(path)

    # Desconhecido: tentar 'strings' como fallback bem genérico.
    errors: List[str] = []
    ret, out, err = _run_cmd(["strings", str(path)])
    if ret == 0 and out.strip():
        errors.append(
            "Extensão desconhecida, texto extraído via 'strings' (resultado pode ser ruidoso)."
        )
        return out, "strings", False, errors

    errors.append(
        f"Extensão desconhecida e 'strings' falhou: rc={ret}, err={err.strip()[:300]}"
    )
    return "", "unknown", False, errors


def extract_file_content(file_path: str) -> Dict[str, Any]:
    """
    Extrai texto de um arquivo usando a melhor estratégia disponível.

    Parâmetros:
        file_path: caminho completo do arquivo a ser extraído.

    Retorno:
        dict com:
            text: str
            extract_method: str
            ocr_used: bool
            errors: [str]
            file_path: str
            size_bytes: int (se disponível)
            sha256: str (hash opcional, útil para auditoria)
    """
    path = pathlib.Path(file_path).expanduser()

    if not path.exists() or not path.is_file():
        return {
            "text": "",
            "extract_method": "not_found",
            "ocr_used": False,
            "errors": [f"Arquivo '{path}' não existe ou não é arquivo."],
            "file_path": str(path),
            "size_bytes": 0,
            "sha256": "",
        }

    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    # Aqui já fazemos o hash, porque é barato e útil para audit.
    sha256 = ""
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        sha256 = h.hexdigest()
    except OSError:
        # Não é crítico falhar no hash.
        pass

    text, method, ocr_used, errors = _guess_extractor(path)

    return {
        "text": text,
        "extract_method": method,
        "ocr_used": ocr_used,
        "errors": errors,
        "file_path": str(path),
        "size_bytes": size,
        "sha256": sha256,
    }


# Opcionalmente, você pode expor um pequeno "main" para testar isolado:
if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) == 2 and sys.argv[1] == "--demo-scan":
        res = scan_directory(max_files=10)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif len(sys.argv) == 2:
        res = extract_file_content(sys.argv[1])
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("Uso:")
        print("  python -m agents.vault-pilot.tools --demo-scan")
        print("  python -m agents.vault-pilot.tools /caminho/para/arquivo.pdf")
EOF

echo "Criado: $TOOLS_FILE"
echo "Concluído."

