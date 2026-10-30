import json
import os
from typing import Dict, Any, Optional
import requests


def generate_heuristic_explanation(item: Dict[str, Any], query: str) -> str:
    """
    Generates a rule-based developer-friendly explanation of why
    this item is relevant to the query without needing any external API.
    """
    reasons = item.get("matched_reasons", [])
    item_type = item.get("type", "definition")
    name = item.get("name", "Unknown")
    file_path = item.get("file_path", "")
    lines = f"L{item.get('start_line')}-L{item.get('end_line')}"
    doc = (item.get("docstring") or "").strip()
    args = item.get("args", [])

    explanation_lines = [
        f"**AST Analysis**: `{name}` is a **{item_type}** declared in `{file_path}` ({lines})."
    ]

    if reasons:
        explanation_lines.append("\n**Key Match Signals:**")
        for r in reasons:
            explanation_lines.append(f"- {r}")

    if args and item_type in ("function", "method"):
        explanation_lines.append(f"- **Signature**: Takes arguments `({', '.join(args)})`.")

    if doc:
        summary_doc = doc.split("\n")[0]
        explanation_lines.append(f"- **Docstring Summary**: \"{summary_doc}\"")

    explanation_lines.append(
        f"\n**Verdict**: Directly addresses the search intent for *\"{query}\"* based on syntax definition and AST symbol extraction."
    )

    return "\n".join(explanation_lines)


def call_llm_api(prompt: str, api_key: str, provider: str = "gemini") -> Optional[str]:
    """
    Lightweight HTTP call to LLM APIs (Gemini or OpenAI compatible) if configured.
    Falls back gracefully if the API fails or quota is exhausted.
    """
    try:
        if provider.lower() == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 200
                }
            }
            res = requests.post(url, json=payload, timeout=8)
            if res.status_code == 200:
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()

        elif provider.lower() == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a concise code search assistant."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 150,
                "temperature": 0.2
            }
            res = requests.post(url, headers=headers, json=payload, timeout=8)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()

    except Exception:
        # Graceful fallback on network errors or timeouts
        return None

    return None


def explain_result(item: Dict[str, Any], query: str, api_key: Optional[str] = None, provider: str = "gemini") -> Dict[str, Any]:
    """
    Explains why a retrieved result matches the query.
    Uses LLM if API key is provided and reachable; otherwise uses smart heuristic.
    """
    clean_key = (api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()

    if clean_key:
        prompt = (
            f"You are CodeLens, an AI code search assistant. "
            f"Explain in 2-3 concise sentences why the following {item.get('type')} `{item.get('name')}` "
            f"in `{item.get('file_path')}` is relevant to the search query: \"{query}\".\n\n"
            f"Source snippet:\n{item.get('source_code', '')[:800]}\n"
        )
        ai_text = call_llm_api(prompt, clean_key, provider=provider)
        if ai_text:
            return {
                "explanation": ai_text,
                "mode": f"AI Powered ({provider.capitalize()})"
            }

    # Fallback / Default heuristic mode
    return {
        "explanation": generate_heuristic_explanation(item, query),
        "mode": "CodeLens AST Heuristic"
    }
