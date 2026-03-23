"""LLM API client. Supports OpenAI, Gemini, and Groq."""

import asyncio
import os

import httpx
from dotenv import load_dotenv

from config import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Priority: OpenAI > Gemini > Groq
if OPENAI_API_KEY:
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
elif GEMINI_API_KEY:
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
else:
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


async def call_llm(prompt: str, temperature: float = 0.0, max_tokens: int = 1024) -> str:
    """Call the configured LLM with retry on rate limits."""
    last_err: Exception | None = None

    for attempt in range(3):
        try:
            if LLM_PROVIDER == "openai":
                return await _call_openai(prompt, temperature, max_tokens)
            elif LLM_PROVIDER == "gemini":
                return await _call_gemini(prompt, temperature, max_tokens)
            elif LLM_PROVIDER == "groq":
                return await _call_groq(prompt, temperature, max_tokens)
            else:
                raise ValueError(f"Unknown LLM provider: {LLM_PROVIDER}")
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
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
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
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
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
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
