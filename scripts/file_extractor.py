#!/usr/bin/env python3
"""
Extração de texto de PDFs com fallback progressivo: PyPDF2 → pdftotext → Tesseract OCR.
OCR pesado (Tesseract) é limitado a pastas /SAUDE/ e /ACADEMICO/, máximo de 100 arquivos por run.
"""
import os
import re
import subprocess
import tempfile

# Pastas onde o OCR completo (Tesseract) é habilitado
_OCR_SCOPE_FOLDERS = frozenset(['/SAUDE/', '/ACADEMICO/', '/FINANCEIRO/'])
_OCR_MAX = 100

_ocr_stats: dict = {'pypdf2': 0, 'pdftotext': 0, 'tesseract': 0, 'tesseract_skipped': 0}

try:
    import PyPDF2 as _PyPDF2
    _HAS_PYPDF2 = True
except ImportError:
    try:
        import pypdf as _PyPDF2  # type: ignore
        _HAS_PYPDF2 = True
    except ImportError:
        _HAS_PYPDF2 = False


def _clean(text: str) -> str:
    """Limpa texto extraído. Threshold de alfa menor (0.20) para preservar linhas com valores médicos."""
    if not text:
        return ""
    text = ''.join(c for c in text if c.isprintable() or c in '\n\r\t')
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if len(line) <= 3:
            lines.append(line)
            continue
        alpha = sum(1 for c in line if c.isalpha())
        if alpha / len(line) > 0.20:
            lines.append(line)
        elif re.search(r'\d', line) and len(line) >= 5:
            # preserva linhas com números (valores de exame, datas, etc.)
            lines.append(line)
    return '\n'.join(lines)


def _pypdf2_extract(path: str, max_pages: int = 3) -> str:
    if not _HAS_PYPDF2:
        return ""
    try:
        with open(path, 'rb') as f:
            reader = _PyPDF2.PdfReader(f)
            total = len(reader.pages)
            if total == 0:
                return ""
            pages = list(range(min(max_pages, total)))
            # também tenta as últimas páginas
            if total > max_pages:
                pages += list(range(max(max_pages, total - 2), total))
            parts = []
            for i in set(pages):
                try:
                    t = reader.pages[i].extract_text()
                    if t:
                        parts.append(t)
                except Exception:
                    pass
        return _clean('\n'.join(parts))
    except Exception:
        return ""


def _pdftotext_extract(path: str) -> str:
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', '-nopgbrk', path, '-'],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            return _clean(result.stdout.decode('utf-8', errors='replace'))
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    return ""


def _tesseract_ocr(path: str, max_pages: int = 2) -> str:
    """Converte as primeiras N páginas do PDF em imagens e aplica OCR."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_prefix = os.path.join(tmpdir, 'page')
            r = subprocess.run(
                ['pdftoppm', '-png', '-r', '150', '-l', str(max_pages), path, out_prefix],
                capture_output=True,
                timeout=60,
            )
            if r.returncode != 0:
                return ""
            texts = []
            for img_name in sorted(os.listdir(tmpdir)):
                if not img_name.endswith('.png'):
                    continue
                img_path = os.path.join(tmpdir, img_name)
                tess = subprocess.run(
                    ['tesseract', img_path, '-', '-l', 'por+eng', '--psm', '3'],
                    capture_output=True,
                    timeout=45,
                )
                if tess.returncode == 0:
                    texts.append(tess.stdout.decode('utf-8', errors='replace'))
            return _clean('\n'.join(texts))
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    return ""


def _in_ocr_scope(path: str) -> bool:
    norm = path.replace('\\', '/').upper()
    return any(folder in norm for folder in _OCR_SCOPE_FOLDERS)


def extract_text_with_ocr(path: str) -> 'tuple[str, bool]':
    """
    Extração progressiva de texto de PDF:
      1. PyPDF2
      2. pdftotext (se PyPDF2 insuficiente)
      3. Tesseract OCR (só em /SAUDE/ e /ACADEMICO/, até _OCR_MAX arquivos/run)

    Retorna (texto, ocr_aplicado).
    """
    # 1. PyPDF2
    text = _pypdf2_extract(path)
    if len(text.strip()) >= 60:
        _ocr_stats['pypdf2'] += 1
        return text, False

    # 2. pdftotext
    pt_text = _pdftotext_extract(path)
    if len(pt_text.strip()) >= 60:
        _ocr_stats['pdftotext'] += 1
        best = pt_text if len(pt_text) > len(text) else text
        return best, False

    # melhor resultado até agora (pode ser vazio)
    combined = pt_text if len(pt_text.strip()) > len(text.strip()) else text

    # 3. Tesseract — apenas em escopo e dentro do limite
    if not _in_ocr_scope(path):
        _ocr_stats['tesseract_skipped'] += 1
        return combined, False

    if _ocr_stats['tesseract'] >= _OCR_MAX:
        _ocr_stats['tesseract_skipped'] += 1
        return combined, False

    ocr_text = _tesseract_ocr(path)
    _ocr_stats['tesseract'] += 1
    best = ocr_text if len(ocr_text.strip()) > len(combined.strip()) else combined
    return best, True


def get_ocr_stats() -> dict:
    return dict(_ocr_stats)
