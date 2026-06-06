#!/usr/bin/env bash
# Translates PT-BR comments/strings in Python files and agent YAML/MD files to English using Gemini CLI.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PROMPT_PY='Translate ALL Portuguese comments (lines starting with # or inside """ """), docstrings, string literals used as messages/errors/output, and variable/function descriptions to English. Keep ALL code logic, imports, variable names, function names, file paths, CLI commands, and technical terms exactly as-is. Keep the #nosec annotations. Return ONLY the translated file content, no explanation, no markdown fences.'

PROMPT_YAML='Translate ALL Portuguese prose to English: descriptions, persona fields, must/must_not rules, when_to_use, when_not_to_use, notes, eval criteria, and any other human-readable text. Keep ALL technical keys, tool names, model names, file paths, and code snippets exactly as-is. Return ONLY the translated file content, no explanation, no markdown fences.'

PROMPT_MD='Translate ALL Portuguese prose to English. Keep ALL code blocks, file paths, CLI commands, YAML snippets, and technical terms exactly as-is. Return ONLY the translated file content, no explanation, no markdown fences.'

translate_file() {
    local file="$1"
    local prompt="$2"
    local tmp
    tmp=$(mktemp)

    echo "  → $file"
    cat "$file" | gemini --yolo -p "$prompt" > "$tmp" 2>/dev/null

    # Only overwrite if gemini returned non-empty content
    if [[ -s "$tmp" ]]; then
        mv "$tmp" "$file"
    else
        rm "$tmp"
        echo "    [SKIP] empty response"
    fi
}

echo "=== Translating Python source files ==="
while IFS= read -r f; do
    # Skip files that are already mostly English (heuristic: <10% PT words)
    translate_file "$f" "$PROMPT_PY"
done < <(find src/ -name "*.py" | sort)

echo ""
echo "=== Translating agent YAML files ==="
while IFS= read -r f; do
    translate_file "$f" "$PROMPT_YAML"
done < <(find agents/ -name "*.yaml" | grep -v runs | sort)

echo ""
echo "=== Translating agent Markdown files ==="
while IFS= read -r f; do
    translate_file "$f" "$PROMPT_MD"
done < <(find agents/ -name "*.md" | grep -v runs | sort)

echo ""
echo "=== Translating real/ and tool_registry/ ==="
while IFS= read -r f; do
    translate_file "$f" "$PROMPT_MD"
done < <(find real/ tool_registry/ -name "*.md" -o -name "*.yaml" 2>/dev/null | grep -v runs | sort)

echo ""
echo "Done. Review with: git diff --stat"
