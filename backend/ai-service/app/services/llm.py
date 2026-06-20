import json
import ssl
import re
import asyncio
import httpx
import logging
from typing import Optional, List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.services.http_client import get_client

logger = logging.getLogger(__name__)

_FUNC_TAG_RE = re.compile(r"<function=([\w\.\-]+)>?\s*(\{.*\})\s*</function>?", re.DOTALL)
_RETRYABLE = (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout, ssl.SSLError)


class LLMRateLimitError(Exception):
    """Raised when Groq's rate limit can't be resolved by a short automatic retry."""
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


def _recover_tool_call_from_failed_generation(raw: str) -> Optional[Dict[str, Any]]:
    """
    Groq's llama-3.3-70b-versatile occasionally wraps a valid tool call in
    <function=name{...}</function> tags instead of emitting clean JSON.
    The model's output is usually correct — only Groq's parser fails.
    Recover the call manually instead of discarding the generation.
    """
    match = _FUNC_TAG_RE.search(raw)
    if not match:
        return None
    name, args_str = match.group(1), match.group(2)
    try:
        args = json.loads(args_str)
    except json.JSONDecodeError:
        return None
    return {
        "id": "recovered_0",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    reraise=True,
)
async def _post_with_retry(url: str, **kwargs):
    client = await get_client()
    return await client.post(url, **kwargs)


class LLMService:
    """
    Handles LLM API calls for the MLOps Copilot.
    Supports Groq (default), OpenAI, and Google Gemini with tool/function calling.
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.timeout = settings.LLM_TIMEOUT

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        result = await self.chat_completion_with_tools(
            messages=messages,
            tools=None,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return result["content"] or ""

    async def chat_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Returns {"content": str | None, "tool_calls": list | None, "finish_reason": str}
        """
        if self.provider in ("groq", "openai"):
            return await self._openai_compatible_completion(
                messages, tools, system_prompt, temperature
            )
        if self.provider == "gemini":
            if tools:
                logger.warning("Gemini provider does not support tool calling; ignoring tools")
            content = await self._gemini_completion(messages, system_prompt, temperature)
            return {"content": content, "tool_calls": None, "finish_reason": "stop"}
        raise ValueError(f"Unknown LLM provider: {self.provider}")

    def _api_base_and_headers(self) -> tuple[str, Dict[str, str]]:
        if self.provider == "groq":
            if not self.api_key:
                raise ValueError("Groq API key not configured (set LLM_API_KEY)")
            return settings.LLM_GROQ_URL, {"Authorization": f"Bearer {self.api_key}"}

        if self.provider == "openai":
            if not self.api_key:
                raise ValueError("OpenAI API key not configured")
            return "https://api.openai.com/v1", {"Authorization": f"Bearer {self.api_key}"}

        raise ValueError(f"Provider {self.provider} is not OpenAI-compatible")

    async def _openai_compatible_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        base_url, headers = self._api_base_and_headers()

        all_messages: List[Dict[str, Any]] = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": all_messages,
            "temperature": 0 if tools else (temperature if temperature is not None else self.temperature),
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        url = f"{base_url}/chat/completions"
        logger.info(
            "Calling %s at %s model=%s tools=%s",
            self.provider,
            url,
            self.model,
            len(tools) if tools else 0,
        )

        response = await _post_with_retry(url, json=payload, headers=headers, timeout=self.timeout)

        # --- malformed tool-call recovery (Groq parser bug) ---
        if response.status_code == 400:
            try:
                err = response.json()["error"]
            except (json.JSONDecodeError, KeyError):
                err = {}
            if err.get("code") == "tool_use_failed" and tools:
                recovered = _recover_tool_call_from_failed_generation(err.get("failed_generation", ""))
                if recovered:
                    logger.warning("Recovered malformed tool call from failed_generation: %s", recovered["function"]["name"])
                    return {
                        "content": None,
                        "tool_calls": [recovered],
                        "finish_reason": "tool_calls",
                    }

        # --- rate limit handling ---
        if response.status_code == 429:
            retry_after = float(response.headers.get("retry-after", 5))
            try:
                err_msg = response.json().get("error", {}).get("message", "Rate limit exceeded")
            except (json.JSONDecodeError, KeyError):
                err_msg = "Rate limit exceeded"

            if retry_after <= 30:
                logger.warning("Rate limited, retrying in %.1fs: %s", retry_after, err_msg)
                await asyncio.sleep(retry_after + 0.5)
                response = await _post_with_retry(url, json=payload, headers=headers, timeout=self.timeout)
            else:
                logger.error("Rate limit needs %.0fs wait, failing fast: %s", retry_after, err_msg)
                raise LLMRateLimitError(err_msg, retry_after=retry_after)

        if response.status_code >= 400:
            logger.error("LLM error %s: %s", response.status_code, response.text)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message = choice["message"]
        return {
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls"),
            "finish_reason": choice.get("finish_reason", "stop"),
        }

    async def _gemini_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        if not self.api_key:
            raise ValueError("Gemini API key not configured")

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})

        for msg in messages:
            if msg.get("role") == "tool":
                continue
            contents.append({"role": msg["role"], "parts": [{"text": msg.get("content", "")}]})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        response = await _post_with_retry(
            url,
            json={
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature or self.temperature,
                    "maxOutputTokens": self.max_tokens,
                },
            },
            params={"key": self.api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def parse_tool_arguments(arguments: Any) -> Dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return {}
    return {}


llm_service = LLMService()