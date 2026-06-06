from __future__ import annotations

import json
import urllib.request
from typing import Any


def _call_ollama(prompt: str, model: str) -> str:
    url = "http://localhost:11434/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = json.loads(r.read())
    return raw.get("response", "")


def _call_gemini(prompt: str, model: str) -> str:
    import os

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY_FOXVAULT")
    if not api_key:
        secrets = __import__("pathlib").Path.home() / ".env.secrets"
        if secrets.exists():
            for line in secrets.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY"):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not defined")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 512},
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = json.loads(r.read())
    return raw["candidates"][0]["content"]["parts"][0]["text"]


_JUDGE_PROMPT = """You are a rigorous technical evaluator of AI agents.

Original question: {input}

Agent response:
{output}

Evaluation criteria:
{criteria}

For each criterion, give a score from 0 to 3:
  0 = absent or inadequate
  1 = attempt with serious gaps
  2 = satisfactory with minor flaws
  3 = excellent

Respond ONLY in valid JSON:
{{"scores": {{"criterion": 0-3}}, "total": sum, "max": total_possible, "pct": percentage, "justifications": {{"criterion": "one sentence"}}}}"""


def score(
    input_text: str,
    output_text: str,
    criteria: list[str],
    judge_model: str,
) -> dict[str, Any]:
    if not criteria:
        return {"skipped": True, "reason": "no criteria defined"}

    criteria_str = "\n".join(f"- {c}" for c in criteria)
    prompt = _JUDGE_PROMPT.format(
        input=input_text,
        output=output_text[:3000],
        criteria=criteria_str,
    )

    try:
        if judge_model.startswith("gemini-"):
            raw = _call_gemini(prompt, judge_model)
        else:
            raw = _call_ollama(prompt, judge_model)
    except Exception as exc:
        return {"error": str(exc)}

    # Parse JSON from response
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        stripped = "\n".join(inner).strip()

    try:
        result = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                result = json.loads(stripped[start:end])
            except json.JSONDecodeError:
                return {"error": "judge parse failed", "raw": raw[:200]}
        else:
            return {"error": "judge parse failed", "raw": raw[:200]}

    max_score = len(criteria) * 3
    total = sum(result.get("scores", {}).values())
    return {
        "scores": result.get("scores", {}),
        "total": total,
        "max": max_score,
        "pct": round(total / max_score * 100) if max_score else 0,
        "justifications": result.get("justifications", {}) or result.get("justificativas", {}),
        "judge_model": judge_model,
    }
