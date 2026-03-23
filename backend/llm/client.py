"""LLM API client. Supports OpenAI, Gemini, and Groq."""

import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv

from config import PROJECT_ROOT

# override=False ensures Railway env vars are NOT overwritten by .env file
load_dotenv(PROJECT_ROOT / ".env", override=False)

logger = logging.getLogger(__name__)


def _get_key(name: str) -> str:
    return os.getenv(name, "")


def _get_provider() -> str:
    if os.getenv("LLM_PROVIDER"):
        return os.getenv("LLM_PROVIDER", "openai")
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    return "groq"


async def call_llm(prompt: str, temperature: float = 0.0, max_tokens: int = 1024) -> str:
    """Call the configured LLM with retry on rate limits."""
    last_err: Exception | None = None

    provider = _get_provider()
    key = _get_key("OPENAI_API_KEY") if provider == "openai" else _get_key("GEMINI_API_KEY") if provider == "gemini" else _get_key("GROQ_API_KEY")
    logger.info(f"LLM provider={provider}, key_length={len(key)}, key_prefix={key[:8]}..." if key else f"LLM provider={provider}, key=EMPTY")
    for attempt in range(3):
        try:
            if provider == "openai":
                return await _call_openai(prompt, temperature, max_tokens)
            elif provider == "gemini":
                return await _call_gemini(prompt, temperature, max_tokens)
            elif provider == "groq":
                return await _call_groq(prompt, temperature, max_tokens)
            else:
                raise ValueError(f"Unknown LLM provider: {provider}")
        except httpx.HTTPStatusError as e:
            last_err = e
            if e.response.status_code == 429 and attempt < 2:
                await asyncio.sleep(2 ** (attempt + 1))
                continue
            raise

    raise last_err  # type: ignore


async def _call_openai(prompt: str, temperature: float, max_tokens: int) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {_get_key('OPENAI_API_KEY')}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_gemini(prompt: str, temperature: float, max_tokens: int) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')}:generateContent?key={_get_key('GEMINI_API_KEY')}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def _call_groq(prompt: str, temperature: float, max_tokens: int) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {_get_key('GROQ_API_KEY')}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
