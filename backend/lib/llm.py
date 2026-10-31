"""LLM service: Featherless AI (OpenAI-compatible) first, Emergent universal key as fallback."""

import asyncio
import json
import logging
import os
import re
import uuid

import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)


class LLMError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def provider_info() -> dict:
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return {
            "provider": "gemini",
            "model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            "configured": True,
        }
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY"):
        return {
            "provider": "claude",
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            "configured": True,
        }
    if os.environ.get("FEATHERLESS_API_KEY"):
        return {
            "provider": "featherless",
            "model": os.environ.get("FEATHERLESS_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct"),
            "configured": True,
        }
    if os.environ.get("EMERGENT_LLM_KEY"):
        return {
            "provider": "emergent",
            "model": f"{os.environ.get('FALLBACK_LLM_PROVIDER', 'anthropic')}/{os.environ.get('FALLBACK_LLM_MODEL', 'claude-sonnet-4-6')}",
            "configured": True,
        }
    return {"provider": "none", "model": "", "configured": False}


async def _gemini(system: str, user: str, max_tokens: int, temperature: float, is_json: bool = False) -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

    gen_config: dict = {
        "maxOutputTokens": max_tokens,
        "temperature": temperature,
    }
    if is_json:
        gen_config["responseMimeType"] = "application/json"

    payload: dict = {
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": gen_config,
    }
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}

    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            try:
                r = await client.post(url, json=payload)
            except httpx.HTTPError as exc:
                raise LLMError(502, f"Could not reach Google Gemini API: {exc}")
            if r.status_code == 429 and attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 429:
                raise LLMError(429, "Google Gemini rate limit reached. Please wait a moment and retry.")
            if r.status_code in (401, 403):
                raise LLMError(502, "Google Gemini rejected the API key. Please check GEMINI_API_KEY in backend/.env.")
            if r.status_code == 503 and attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            if r.status_code >= 400:
                try:
                    err_msg = r.json().get("error", {}).get("message", r.text[:300])
                except Exception:
                    err_msg = r.text[:300]
                raise LLMError(502, f"Gemini API error: {err_msg}")
            data = r.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            text_parts = [p.get("text", "") for p in parts if "text" in p]
            return "".join(text_parts) or ""
    raise LLMError(502, "Google Gemini did not respond")


async def _anthropic(system: str, user: str, max_tokens: int, temperature: float) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    async with httpx.AsyncClient(timeout=120) as client:
        for attempt in range(3):
            try:
                r = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
            except httpx.HTTPError as exc:
                raise LLMError(502, f"Could not reach Anthropic Claude API: {exc}")
            if r.status_code == 429 and attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 429:
                raise LLMError(429, "Claude rate limit reached. Please wait a moment and retry.")
            if r.status_code in (401, 403):
                raise LLMError(502, "Anthropic rejected the API key. Update ANTHROPIC_API_KEY in backend/.env.")
            if r.status_code == 400:
                try:
                    err_data = r.json().get("error", {})
                    msg = err_data.get("message", r.text[:300])
                except Exception:
                    msg = r.text[:300]
                raise LLMError(400, f"Claude API error: {msg}")
            if r.status_code >= 400:
                raise LLMError(502, f"Claude API error {r.status_code}: {r.text[:300]}")
            data = r.json()
            content_blocks = data.get("content", [])
            text_blocks = [b["text"] for b in content_blocks if b.get("type") == "text"]
            return "".join(text_blocks) or ""
    raise LLMError(502, "Claude API did not respond")


async def _featherless(system: str, user: str, max_tokens: int, temperature: float) -> str:
    base = os.environ.get("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1").rstrip("/")
    payload = {
        "model": os.environ.get("FEATHERLESS_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct"),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {os.environ['FEATHERLESS_API_KEY']}"}
    async with httpx.AsyncClient(timeout=120) as client:
        for attempt in range(3):
            try:
                r = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
            except httpx.HTTPError as exc:
                raise LLMError(502, f"Could not reach Featherless AI: {exc}")
            if r.status_code == 429 and attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 429:
                raise LLMError(429, "Featherless AI rate limit reached. Please wait a moment and retry.")
            if r.status_code in (401, 403):
                raise LLMError(502, "Featherless AI rejected the API key. Update FEATHERLESS_API_KEY in Settings.")
            if r.status_code >= 400:
                raise LLMError(502, f"Featherless AI error {r.status_code}: {r.text[:300]}")
            data = r.json()
            return data["choices"][0]["message"]["content"] or ""
    raise LLMError(502, "Featherless AI did not respond")


async def _emergent(system: str, user: str) -> str:
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=str(uuid.uuid4()), system_message=system).with_model(
        os.environ.get("FALLBACK_LLM_PROVIDER", "anthropic"), os.environ.get("FALLBACK_LLM_MODEL", "claude-sonnet-4-6")
    )
    try:
        return await chat.send_message(UserMessage(text=user))
    except Exception as exc:  # provider errors surface as a clear 502, never a fake answer
        msg = str(exc)
        if "429" in msg or "rate" in msg.lower():
            raise LLMError(429, "AI rate limit reached. Please wait a moment and retry.")
        raise LLMError(502, f"AI provider error: {msg[:300]}")


async def complete(system: str, user: str, max_tokens: int = 2000, temperature: float = 0.3, is_json: bool = False) -> str:
    info = provider_info()
    if info["provider"] == "gemini":
        return await _gemini(system, user, max_tokens, temperature, is_json=is_json)
    if info["provider"] == "claude":
        return await _anthropic(system, user, max_tokens, temperature)
    if info["provider"] == "featherless":
        return await _featherless(system, user, max_tokens, temperature)
    if info["provider"] == "emergent":
        return await _emergent(system, user)
    raise LLMError(503, "No AI provider is configured. Add GEMINI_API_KEY, ANTHROPIC_API_KEY, or FEATHERLESS_API_KEY to enable AI answers.")


def parse_json(text: str) -> dict:
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence and "{" in fence.group(1):
        t = fence.group(1)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(t[start : end + 1])


async def complete_json(system: str, user: str, max_tokens: int = 3000) -> dict:
    sys = system + "\nRespond with ONLY one valid JSON object. No prose, no markdown fences."
    text = await complete(sys, user, max_tokens=max_tokens, temperature=0.2, is_json=True)
    try:
        return parse_json(text)
    except (ValueError, json.JSONDecodeError):
        logger.warning("LLM returned invalid JSON, retrying once")
        text = await complete(sys, user + "\n\nYour previous reply was not valid JSON. Return ONLY the JSON object.", max_tokens=max_tokens, temperature=0.1, is_json=True)
        try:
            return parse_json(text)
        except (ValueError, json.JSONDecodeError):
            raise LLMError(502, "The AI returned a malformed response. Please try again.")


MODE_STYLES = {
    "beginner": (
        "AUDIENCE: a complete beginner with little or no programming knowledge. Use simple, friendly language. "
        "Define every technical term the first time you use it. Use one relatable everyday analogy where useful. "
        "Break the explanation into small numbered steps and explain what each important section of code does."
    ),
    "student": (
        "AUDIENCE: a computer-science student with basic programming knowledge. Explain the concepts and the "
        "implementation details, use correct technical terminology with short explanations, discuss logic, functions, "
        "dependencies and execution order, and include a small useful example when it helps."
    ),
    "expert": (
        "AUDIENCE: an experienced engineer. Be concise and technically dense. Focus on architecture, implementation, "
        "dependencies, edge cases, complexity/performance and design trade-offs. Skip beginner-level explanations."
    ),
}


def mode_style(mode: str) -> str:
    return MODE_STYLES.get(mode, MODE_STYLES["student"])
