from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

# Constants for tool output compression
_TOKEN_THRESHOLD = 800  # heurístico baseado no V1

# Constants for fuzzy matching (V5.1)
SCORE_FUZZY_MIN = 0.80       # minimum score to consider a fuzzy match
SCORE_AMBIGUOUS_MIN = 0.50    # minimum score to avoid "none"
DELTA_MIN = 0.15             # minimum delta between top-1 and top-2 for fuzzy


def _summarize_scan_output(tool_data: dict, mode: str = "full", max_items: int = 20) -> dict:
    """
    Transforma o tool_data de scan_directory em diferentes formatos para benchmark.
    mode: "full" | "top_n" | "summary" | "by_folder" | "plain_text"

    Esta função NÃO altera o comportamento padrão do engine.
    Uso destinado exclusivamente a scripts de benchmark e testes internos.
    """
    files = tool_data.get("files", [])
    total = tool_data.get("file_count", len(files))
    base = tool_data.get("directory", "")

    if mode == "full":
        return tool_data

    if mode == "top_n":
        return {
            "directory": base,
            "file_count": total,
            "showing": min(max_items, total),
            "files": [
                {"path": f.get("path"), "extension": f.get("extension")}
                for f in files[:max_items]
            ],
        }

    if mode == "summary":
        ext_count = Counter(f.get("extension") for f in files)
        folder_count = Counter(
            str(Path(f.get("path") or "raiz").parent)
            for f in files
        )
        return {
            "directory": base,
            "total_files": total,
            "by_extension": dict(ext_count.most_common(10)),
            "by_folder": dict(folder_count.most_common(10)),
            "sample_files": [f.get("path") for f in files[:5]],
        }

    if mode == "by_folder":
        folders: dict[str, list[str]] = defaultdict(list)
        for f in files:
            path = f.get("path") or ""
            parts = path.split("/")
            folder = "/".join(parts[:-1]) if len(parts) > 1 else "raiz"
            folders[folder].append(f.get("name") or path)
        return {
            "directory": base,
            "total_files": total,
            "folders": {
                k: {"count": len(v), "examples": v[:3]}
                for k, v in list(folders.items())[:15]
            },
        }

    if mode == "plain_text":
        lines = [f"Diretório: {base}", f"Total: {total} arquivos", ""]
        for f in files[:max_items]:
            lines.append(f"- {f.get('path')}")
        if total > max_items:
            lines.append(f"... e mais {total - max_items} arquivos")
        return {"_text": "\n".join(lines)}

    return tool_data


def _maybe_compress_tool_output(tool_data: dict, tool_name: str) -> dict:
    """
    Comprime tool outputs grandes automaticamente antes de injetar no prompt.
    Usado inicialmente no vault-pilot como PoC.
    """
    try:
        estimated_tokens = len(json.dumps(tool_data)) // 4
    except TypeError:
        return tool_data

    if estimated_tokens <= _TOKEN_THRESHOLD:
        return tool_data

    if tool_name == "scan_directory":
        return _summarize_scan_output(tool_data, mode="summary")

    if any(k in tool_data for k in ("files", "items", "results")):
        return _summarize_scan_output(tool_data, mode="top_n", max_items=20)

    return tool_data


def _build_input_with_file_content(
    input_text: str,
    file_text: str,
    mode: str = "current_tag",
    tool_prefix: str = "",
) -> str:
    """
    Monta o prompt injetando conteúdo de documento em diferentes formatos.
    mode: "current_tag" | "tool_response_tag" | "plain_block" |
          "instruction_strong" | "instruction_role" | "content_last" |
          "no_tag"

    Esta função NÃO altera o comportamento padrão do engine.
    Uso destinado exclusivamente a benchmarks e testes internos.
    """
    if mode == "current_tag":
        return f"{tool_prefix}<file_content>\n{file_text}\n</file_content>\n\nUser: {input_text}"

    if mode == "tool_response_tag":
        return f"{tool_prefix}<tool_response>\n{file_text}\n</tool_response>\n\nUser: {input_text}"

    if mode == "plain_block":
        return (
            f"{tool_prefix}CONTEÚDO DO ARQUIVO:\n"
            f"---\n{file_text}\n---\n\n"
            f"User: {input_text}"
        )

    if mode == "instruction_strong":
        return (
            f"{tool_prefix}NÃO chame nenhuma ferramenta. "
            f"Use APENAS o texto abaixo para responder.\n\n"
            f"{file_text}\n\n"
            f"User: {input_text}"
        )

    if mode == "instruction_role":
        return (
            f"{tool_prefix}Você recebeu o seguinte documento. "
            f"Analise-o sem chamar nenhuma ferramenta:\n\n"
            f"{file_text}\n\n"
            f"User: {input_text}"
        )

    if mode == "content_last":
        return (
            f"{tool_prefix}User: {input_text}\n\n"
            f"Conteúdo do documento:\n{file_text}"
        )

    if mode == "no_tag":
        return f"{tool_prefix}{file_text}\n\nUser: {input_text}"

    return f"{tool_prefix}{file_text}\n\nUser: {input_text}"


def _normalize_path_name(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9_/.\- ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_query_name(utterance: str, file_paths: list[str] | None = None) -> dict:
    """
    Extrai informações sobre o arquivo alvo a partir do utterance.

    Pipeline em camadas (V5.1):
      1. Camada 1 — Match de path completo (substring case-insensitive em file_paths).
      2. Camada 2 — Basename com extensão (aspas ou regex robusta permitindo espaços).
      3. Camada 3 — Fallback baseado em tokens fortes (removendo stopwords PT).

    Retorna dict com:
      - query_name: str | None (termo extraído, se houver)
      - match_hint_path: str | None (path completo se Camada 1 acionar)
      - tokens: list[str] | None (tokens fortes extraídos, normalizados)
      - extraction_source: str ("full_path_substring" | "quoted_or_extension" | "tokens_fallback" | "none")
    """
    file_paths = file_paths or []

    # ------------------------------------------------------------------
    # Camada 1 — Match de path completo
    # ------------------------------------------------------------------
    utterance_norm = _normalize_path_name(utterance)
    for fp in file_paths:
        fp_norm = _normalize_path_name(fp)
        if fp_norm and fp_norm in utterance_norm:
            return {
                "query_name": None,
                "match_hint_path": fp,
                "tokens": None,
                "extraction_source": "full_path_substring",
            }

    # ------------------------------------------------------------------
    # Camada 2 — Basename com extensão (aspas ou padrão robusto)
    # ------------------------------------------------------------------
    # Palavras de instrução a remover do início de candidatos capturados pelo regex
    _INSTR_WORDS = {
        "analise", "analisar", "mostre", "mostrar", "me", "o", "a", "os", "as",
        "um", "uma", "do", "da", "de", "dos", "das", "em", "no", "na",
        "arquivo", "documento", "pode", "poderia", "preciso", "quero",
        "ver", "veja", "abrir", "abra", "ler", "leia", "extraia", "use",
        "utilize", "sobre", "traga", "fale", "pro", "pra", "ao", "por",
        "favor", "please", "que", "para", "com",
    }

    # 2a. Texto entre aspas (duplas ou simples) — usa a mais longa
    quoted = re.findall(r'["\']([^"\']+)["\']', utterance)
    if quoted:
        candidate = max(quoted, key=len)
        # Extract tokens from quoted name for compound matching
        qtokens = re.findall(r"\b[\w\-]+\b", _normalize_path_name(candidate))
        qtokens = [t for t in qtokens if len(t) > 1 and not t.endswith(("pdf", "docx", "doc", "odt", "xlsx", "txt", "csv", "pptx", "ppt"))]
        return {
            "query_name": candidate,
            "match_hint_path": None,
            "tokens": qtokens or None,
            "extraction_source": "quoted_or_extension",
        }

    # 2b. Padrão com extensão — captura greedy, depois remove palavras de instrução
    #     do início da captura para isolar o nome do arquivo.
    m = re.search(
        r'([\w\s\-_]+\.(?:pdf|docx?|odt|pptx?|xlsx?|txt|csv))',
        utterance,
        flags=re.IGNORECASE,
    )
    if m:
        candidate = m.group(1).strip()
        # Strip leading instruction words to isolate the actual filename
        parts = candidate.split()
        while parts and parts[0].lower() in _INSTR_WORDS:
            parts.pop(0)
        if parts:
            candidate = " ".join(parts)
        if " " in candidate or len(candidate) > 12:
            # Extract tokens from the filename portion (without extension)
            name_no_ext = re.sub(r'\.(?:pdf|docx?|odt|pptx?|xlsx?|txt|csv)$', '', candidate, flags=re.IGNORECASE)
            etokens = re.findall(r"\b[\w\-]+\b", _normalize_path_name(name_no_ext))
            etokens = [t for t in etokens if len(t) > 1]
            return {
                "query_name": candidate,
                "match_hint_path": None,
                "tokens": etokens or None,
                "extraction_source": "quoted_or_extension",
            }

    # ------------------------------------------------------------------
    # Camada 3 — Fallback baseado em tokens fortes
    # ------------------------------------------------------------------
    _PT_STOPWORDS = {
        "o", "a", "os", "as", "um", "uma", "uns", "umas",
        "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
        "com", "por", "para", "que", "e", "ou", "mas", "se", "ao", "aos",
        "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas",
        "me", "te", "se", "nos", "vos", "lhe", "lhes",
        "e", "sao", "foi", "era", "ser", "estar", "tem",
        "analise", "analisar", "extraia", "extrair", "descreva", "describe",
        "qual", "quais", "onde", "quando", "como", "por", "que",
        "arquivo", "documento", "relatorio",
        "ver", "mostre", "traga", "fale", "sobre", "existe",
        # Verbos e palavras de instrução adicionais
        "preciso", "quero", "posso", "pode", "poderia", "gostaria",
        "use", "utilize", "usar", "abrir", "abra", "ler", "leia",
        "veja", "vejo", "analisar", "analisando", "extraindo",
        "mostre", "mostra", "apresente", "apresenta",
        # Substantivos genéricos que aparecem em instruções
        "pasta", "geral", "resumo", "principais", "pontos",
        "numero", "numeros", "dados", "atualizados", "atualizado",
        "copia", "versao", "tipo", "via", "mais",
        "conteudo", "informacoes", "informacao", "detalhes",
        "favor", "please", "voce", "ele", "ela",
        # Preposições / conjunções extras
        "pra", "pro", "ate", "apos", "antes", "depois", "tambem",
        "bem", "assim", "entao", "logo", "ja", "nao", "sim",
        # Verbos e substantivos genéricos adicionais (comuns em perguntas longas)
        "ferramentas", "pontos", "verifique", "verificar", "explicar", "consta",
        "estao", "assinou", "assinado", "recentemente", "algum", "alguma",
        "acesse", "acessar", "salve", "salvar", "envie", "enviar",
    }

    # Nomes próprios que NÃO devem ser filtrados (pessoas do vault)
    _PROPER_NAMES = {
        "conrado", "nogueira", "emilia", "chaves", "oliveira",
        "maria", "joao", "gonzaga", "luiz", "rafael", "silvana",
        "katia", "lorena", "eduarda", "luiza",
    }

    tokens_raw = re.findall(r"\b[\w\-]+\b", utterance.lower())
    # Normalizar ANTES de checar stopwords: "está"→"esta", "são"→"sao", "você"→"voce"
    tokens_norm_pairs = [(t, _normalize_path_name(t)) for t in tokens_raw]
    tokens_norm_pairs = [(t, n) for t, n in tokens_norm_pairs if n and (len(n) > 1 or n in _PROPER_NAMES)]
    # Manter tokens cujo form normalizado NÃO está em stopwords, OU é nome próprio
    tokens_strong_norm = [
        n for _, n in tokens_norm_pairs
        if (n not in _PT_STOPWORDS) or (n in _PROPER_NAMES)
    ]

    if tokens_strong_norm:
        query_name = " ".join(tokens_strong_norm)
        return {
            "query_name": query_name,
            "match_hint_path": None,
            "tokens": tokens_strong_norm,
            "extraction_source": "tokens_fallback",
        }

    return {
        "query_name": None,
        "match_hint_path": None,
        "tokens": None,
        "extraction_source": "none",
    }


def _extract_filename_intent_fuzzy(
    user_utterance: str,
    file_paths: list[str],
) -> dict:
    """
    Versão experimental/fuzzy de resolução de path de arquivo (V5.1).

    Parâmetros:
      user_utterance : texto completo da pergunta do usuário
      file_paths     : lista de paths disponíveis (relativos ao staging,
                       ex.: ["CONRADO/GERAL/Contrato Conrado Nogueira.pdf", ...])

    Retorna:
      {
        "match_type":    "exact" | "fuzzy" | "ambiguous" | "none",
        "resolved_path": str | None,
        "candidates":    [{"path": str, "score": float, "reason": str}, ...]
                         (sempre presente, ordenada por score desc)
        "extraction":    resultado de _extract_query_name (para debug)
      }

    Regras de decisão (V5.1):
      - exact:
          * match_hint_path presente e válido, OU
          * score_top1 == 1.0 e único
      - fuzzy:
          * score_top1 >= SCORE_FUZZY_MIN (0.80)
          * delta >= DELTA_MIN (0.15)
          * tokens fortes (se houver) todos presentes no basename
      - ambiguous:
          * score_top1 >= SCORE_AMBIGUOUS_MIN (0.50) mas delta < DELTA_MIN,
            ou múltiplos candidatos com tokens semelhantes
      - none:
          * score_top1 < SCORE_AMBIGUOUS_MIN, ou
          * nenhum candidato satisfaz regras de tokens

    Esta função NÃO deve ser usada no runtime.
    Uso exclusivo para benchmarks/experiments V5/V5.1.
    """
    # Step 1: Extract query information using the new pipeline
    extraction = _extract_query_name(user_utterance, file_paths)
    query_name = extraction["query_name"]
    match_hint_path = extraction["match_hint_path"]
    tokens = extraction["tokens"] or []

    # Normalize query if present
    query_norm = _normalize_path_name(query_name) if query_name else ""
    query_tokens = set(tokens)  # tokens already normalized from _extract_query_name

    # Step 2: If match_hint_path is present, treat as exact match candidate
    if match_hint_path and match_hint_path in file_paths:
        # Verify it's actually in the list
        return {
            "match_type": "exact",
            "resolved_path": match_hint_path,
            "candidates": [{"path": match_hint_path, "score": 1.0, "reason": "full_path_substring"}],
            "extraction": extraction,
        }

    # Preferência de extensão para desempate (menor = mais preferido)
    _EXT_RANK = {".pdf": 0, ".docx": 1, ".doc": 2, ".odt": 3, ".xlsx": 4, ".txt": 5}

    def _file_rank(path: str) -> tuple[int, int]:
        """Critério de desempate: extensão preferida e sem sufixo de versão (_2, _3...)."""
        ext = os.path.splitext(path)[1].lower()
        ext_pref = _EXT_RANK.get(ext, 10)
        # Penaliza arquivos com sufixo versão: _2.pdf, _2.docx etc.
        has_version = 1 if re.search(r'_\d+\.[a-z]+$', path, re.IGNORECASE) else 0
        return (ext_pref, has_version)

    # Step 3: Pre-filter by ALL tokens when tokens were extracted (qualquer fonte)
    paths_to_score = list(file_paths)
    if query_tokens:
        eligible = [
            p for p in file_paths
            if all(tok in _normalize_path_name(os.path.basename(p)) for tok in query_tokens)
        ]
        if eligible:
            paths_to_score = eligible
        else:
            # Nenhum arquivo contém todos os tokens → arquivo não existe
            return {
                "match_type": "none",
                "resolved_path": None,
                "candidates": [],
                "extraction": extraction,
            }

    # Step 4: Score candidates
    candidates = []
    for path in paths_to_score:
        basename = os.path.basename(path)
        basename_norm = _normalize_path_name(basename)
        dir_norm = _normalize_path_name(os.path.dirname(path))

        # Base score: SequenceMatcher contra BASENAME
        if query_norm:
            base_score = SequenceMatcher(None, query_norm, basename_norm).ratio()
        else:
            base_score = 0.0

        # Substring hit (query_norm contida em basename ou vice-versa)
        substr_hit = bool(query_norm and (query_norm in basename_norm or basename_norm in query_norm))

        # Tokens: usar basename SEM extensão para set-membership (evita "nogueira.pdf" ≠ "nogueira")
        basename_clean = re.sub(
            r'\.(?:pdf|docx?|odt|pptx?|xlsx?|txt|csv)$', '', basename_norm, flags=re.IGNORECASE
        )
        basename_tokens = set(basename_clean.split()) - {""}

        # Token overlap via set-membership (tokens normalizados vs basename sem extensão)
        if query_tokens:
            overlap = len(query_tokens & basename_tokens) / len(query_tokens)
        else:
            overlap = 0.0

        # Per-token substring bonus: cada token individualmente encontrado como substring no basename
        # Cobre casos como "emilia" dentro de "emiliac" ou "rg" dentro de "rgmariaemilia"
        tok_substr_ratio = 0.0
        if query_tokens:
            hits = sum(1 for tok in query_tokens if tok in basename_norm)
            tok_substr_ratio = hits / len(query_tokens)

        # Two-tier token bonus: exact word membership (strong) vs substring-only (weak)
        tok_word_ratio = overlap  # fraction of query_tokens exact in basename_tokens
        tok_substr_only_ratio = max(0.0, tok_substr_ratio - tok_word_ratio)

        score = base_score
        if substr_hit:
            score += 0.15
        score += 0.30 * tok_word_ratio           # strong: token is a complete word in basename
        if query_tokens and query_tokens.issubset(basename_tokens):
            score += 0.15                         # extra: ALL tokens matched as complete words
        score += 0.08 * tok_substr_only_ratio     # weak: token found only as substring
        if query_tokens and dir_norm:
            dir_tokens = set(dir_norm.split())
            if query_tokens & dir_tokens:
                score += 0.05
        score = min(1.0, score)

        reasons = []
        if substr_hit:
            reasons.append("substr")
        if overlap > 0:
            reasons.append(f"overlap={overlap:.2f}")
        if tok_substr_ratio > 0:
            reasons.append(f"tok_sub={tok_substr_ratio:.2f}")
        if not reasons:
            reasons.append("seq_only")

        candidates.append({
            "path": path,
            "score": round(score, 4),
            "reason": ", ".join(reasons),
        })

    # Ordenar: score desc, depois critério de desempate (ext preferida, não-versão)
    candidates.sort(key=lambda c: (-c["score"], _file_rank(c["path"])))

    if not candidates:
        return {
            "match_type": "none",
            "resolved_path": None,
            "candidates": [],
            "extraction": extraction,
        }

    score_top1 = candidates[0]["score"]
    score_top2 = candidates[1]["score"] if len(candidates) > 1 else 0.0
    delta = score_top1 - score_top2

    # Step 5: Decision rules (V5.1)
    # Exact: score 1.0 único (após desempate por _file_rank, top1 já é o preferido)
    if score_top1 == 1.0 and (len(candidates) == 1 or candidates[1]["score"] < 1.0):
        return {
            "match_type": "exact",
            "resolved_path": candidates[0]["path"],
            "candidates": candidates[:3],
            "extraction": extraction,
        }

    # Fuzzy match
    if score_top1 >= SCORE_FUZZY_MIN and delta >= DELTA_MIN:
        if query_tokens:
            basename_top = _normalize_path_name(os.path.basename(candidates[0]["path"]))
            all_tokens_present = all(tok in basename_top for tok in query_tokens)
            if not all_tokens_present:
                if score_top1 >= SCORE_AMBIGUOUS_MIN:
                    return {
                        "match_type": "ambiguous",
                        "resolved_path": None,
                        "candidates": candidates[:3],
                        "extraction": extraction,
                    }
                return {
                    "match_type": "none",
                    "resolved_path": None,
                    "candidates": candidates[:3],
                    "extraction": extraction,
                }
        return {
            "match_type": "fuzzy",
            "resolved_path": candidates[0]["path"],
            "candidates": candidates[:3],
            "extraction": extraction,
        }

    # Ambiguous
    if score_top1 >= SCORE_AMBIGUOUS_MIN:
        return {
            "match_type": "ambiguous",
            "resolved_path": None,
            "candidates": candidates[:3],
            "extraction": extraction,
        }

    # None
    return {
        "match_type": "none",
        "resolved_path": None,
        "candidates": candidates[:3],
        "extraction": extraction,
    }
