import httpx
import logging
from typing import Optional, List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Handles LLM API calls for the AI copilot.
    Supports OpenAI, Ollama, and Google Gemini.
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
        if self.provider == "openai":
            return await self._openai_completion(messages, system_prompt, temperature)
        elif self.provider == "ollama":
            return await self._ollama_completion(messages, system_prompt, temperature)
        elif self.provider == "gemini":
            return await self._gemini_completion(messages, system_prompt, temperature)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    async def _openai_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")

        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": all_messages,
                    "temperature": temperature or self.temperature,
                    "max_tokens": self.max_tokens,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def _ollama_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        ollama_url = f"{settings.LLM_OLLAMA_URL}/api/chat"
        logger.info(f"Calling Ollama at {ollama_url} with model={self.model}")

        ollama_timeout = httpx.Timeout(
            connect=10.0,
            read=self.timeout,
            write=10.0,
            pool=5.0,
        )

        async with httpx.AsyncClient(timeout=ollama_timeout) as client:
            response = await client.post(
                ollama_url,
                json={
                    "model": self.model,
                    "messages": all_messages,
                    "options": {
                        "temperature": temperature or self.temperature,
                        "num_predict": settings.LLM_MAX_TOKENS,  # respect config, no hard cap
                        "num_ctx": 4096,         # full context window
                        "repeat_penalty": 1.1,   # reduce repetition
                        "top_p": 0.9,            # nucleus sampling for quality
                        "top_k": 40,
                    },
                    "stream": False,
                },
            )
            logger.info(f"Ollama response status: {response.status_code}")
            response.raise_for_status()
            return response.json()["message"]["content"]

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
            contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                json={
                    "contents": contents,
                    "generationConfig": {
                        "temperature": temperature or self.temperature,
                        "maxOutputTokens": self.max_tokens,
                    },
                },
                params={"key": self.api_key},
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]


# Global instance
llm_service = LLMService()