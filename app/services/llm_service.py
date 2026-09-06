"""
app/services/llm_service.py

Provider-agnostic LLM caller. This is the ONLY file in the project
with provider-specific code. Everything else calls `call_llm()` and
doesn't care which provider is configured.

Supported providers (set via LLM_PROVIDER in .env):
  openai    — OpenAI API (gpt-4o, gpt-4o-mini, etc.)
  anthropic — Anthropic API (claude-3-haiku, etc.)
  gemini    — Google Gemini API
  groq      — Groq API (fast inference, free tier)
  ollama    — Local Ollama instance (no API key needed)
"""

import os
from dotenv import load_dotenv

load_dotenv()  # read .env file into os.environ at import time

# Read config once at module load — all route code uses call_llm() directly
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower().strip()
LLM_API_KEY  = os.getenv("LLM_API_KEY", "")
LLM_MODEL    = os.getenv("LLM_MODEL", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")  # optional; mainly for Ollama


def call_llm(prompt_text: str) -> str:
    """
    Send `prompt_text` to the configured LLM and return the text response.
    Raises ValueError for unsupported providers, RuntimeError on API errors.
    """
    if not LLM_PROVIDER:
        raise ValueError("LLM_PROVIDER is not set in .env")

    if LLM_PROVIDER == "openai":
        return _call_openai(prompt_text)
    elif LLM_PROVIDER == "anthropic":
        return _call_anthropic(prompt_text)
    elif LLM_PROVIDER == "gemini":
        return _call_gemini(prompt_text)
    elif LLM_PROVIDER == "groq":
        return _call_groq(prompt_text)
    elif LLM_PROVIDER == "ollama":
        return _call_ollama(prompt_text)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: '{LLM_PROVIDER}'. "
                         f"Choose from: openai, anthropic, gemini, groq, ollama")


# ── Provider implementations ──────────────────────────────────────
# Each function is self-contained. Imports are local to avoid
# ImportError if a provider's package isn't installed.

def _call_openai(prompt_text: str) -> str:
    """OpenAI Chat Completions API (also works for Groq — same SDK, different base_url)."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: uv add openai")

    client = OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL or None,  # None = use OpenAI default; override for proxies
    )
    response = client.chat.completions.create(
        model=LLM_MODEL or "gpt-4o-mini",
        messages=[{"role": "user", "content": prompt_text}],
    )
    return response.choices[0].message.content


def _call_anthropic(prompt_text: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: uv add anthropic")

    client = anthropic.Anthropic(api_key=LLM_API_KEY)
    message = client.messages.create(
        model=LLM_MODEL or "claude-3-haiku-20240307",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt_text}],
    )
    return message.content[0].text


def _call_gemini(prompt_text: str) -> str:
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError("google-generativeai package not installed. Run: uv add google-generativeai")

    genai.configure(api_key=LLM_API_KEY)
    model = genai.GenerativeModel(LLM_MODEL or "gemini-1.5-flash")
    response = model.generate_content(prompt_text)
    return response.text


def _call_groq(prompt_text: str) -> str:
    """
    Groq uses the OpenAI-compatible SDK with a different base_url.
    We reuse the OpenAI client — just point it at Groq's endpoint.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: uv add openai")

    client = OpenAI(
        api_key=LLM_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )
    response = client.chat.completions.create(
        model=LLM_MODEL or "llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt_text}],
    )
    return response.choices[0].message.content


def _call_ollama(prompt_text: str) -> str:
    """
    Ollama runs locally — no API key needed.
    Default endpoint: http://localhost:11434
    Override with LLM_BASE_URL in .env if running on a different port.
    Uses the OpenAI-compatible endpoint that Ollama exposes.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: uv add openai")

    base_url = LLM_BASE_URL or "http://localhost:11434"
    # Ollama's OpenAI-compatible endpoint lives at /v1
    if not base_url.endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    client = OpenAI(
        api_key="ollama",   # Ollama ignores the key but the SDK requires a non-empty string
        base_url=base_url,
    )
    response = client.chat.completions.create(
        model=LLM_MODEL or "llama3",
        messages=[{"role": "user", "content": prompt_text}],
    )
    return response.choices[0].message.content
