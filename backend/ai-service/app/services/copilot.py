import httpx
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from app.services.llm import llm_service
from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an MLOps AI assistant embedded in an ML platform. You help data scientists and ML engineers understand their models, data drift, SHAP explanations, and training results.

Rules:
- Be concise and direct. Lead with the answer, then explain.
- When given JSON data, always reference the actual numbers in your response.
- For drift: always state severity (low/medium/high) first, then detail.
- For SHAP: identify the top 3 positive and top 3 negative features by name.
- For model comparison: always name a winner and justify it in one sentence.
- Never say "I cannot" — if data is missing, say what you'd need and give a best-effort answer.
- Use plain language. No unnecessary jargon."""


class AIContext:
    """Maintains conversation context with a sliding window to avoid token overload."""

    def __init__(self, max_messages: int = None):
        self.messages: List[Dict[str, str]] = []
        self.max_messages = max_messages or settings.LLM_MAX_CONTEXT_MESSAGES
        self.system_prompt = SYSTEM_PROMPT

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        # Trim oldest pair when over limit — always drop 2 to keep user/assistant pairs intact
        while len(self.messages) > self.max_messages:
            self.messages = self.messages[2:]

    def get_messages(self) -> List[Dict[str, str]]:
        return self.messages.copy()

    def clear(self):
        self.messages = []


class MLOpsDataFetcher:
    """Fetches live data from MLOps services to ground the AI in real context."""

    async def get_model_info(self, model_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                endpoint = f"{settings.DEPLOYMENT_SERVICE_URL}/models/{model_name}"
                if version:
                    endpoint += f"?version={version}"
                response = await client.get(endpoint)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning(f"Could not fetch model info for {model_name}: {e}")
            return {}

    async def get_drift_report(self, model_name: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.MONITORING_SERVICE_URL}/drift/{model_name}"
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning(f"Could not fetch drift report for {model_name}: {e}")
            return {}

    async def get_monitoring_metrics(self, model_name: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.MONITORING_SERVICE_URL}/metrics/{model_name}"
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning(f"Could not fetch metrics for {model_name}: {e}")
            return {}


class SHAPExplainer:
    """Explains SHAP outputs in natural language."""

    async def explain_shap(self, shap_data: Dict[str, Any], context: AIContext) -> str:
        if not shap_data or "values" not in shap_data:
            return "No SHAP data provided. Please pass base_value, values (dict of feature→contribution), and optionally feature names."

        values = shap_data.get("values", {})

        # BUG FIX: values may be a list (per-sample array) not a dict.
        # Normalise to {feature_name: contribution} before sorting.
        if isinstance(values, list):
            feature_names = shap_data.get("feature_names", [f"feature_{i}" for i in range(len(values))])
            values = dict(zip(feature_names, values))

        sorted_features = sorted(values.items(), key=lambda x: abs(float(x[1])), reverse=True)
        top_features = sorted_features[:10]

        prompt = f"""Explain this SHAP output for a machine learning prediction.

Base value (average prediction): {shap_data.get('base_value', 'N/A')}
Final prediction: {shap_data.get('prediction', 'N/A')}

Top feature contributions (name: impact):
{json.dumps(dict(top_features), indent=2)}

Give a 3-4 sentence explanation: which features pushed the prediction up, which pushed it down, and what this means for the end user."""

        context.add_message("user", prompt)
        response = await llm_service.chat_completion(
            context.get_messages(),
            system_prompt=context.system_prompt,
        )
        context.add_message("assistant", response)
        return response


class DriftAnalyzer:
    """Analyzes and explains model and data drift."""

    async def explain_drift(self, drift_report: Dict[str, Any], context: AIContext) -> str:
        if not drift_report:
            return "No drift report available. Provide drift metrics to get an analysis."

        prompt = f"""Analyze this model drift report and give a clear recommendation.

{json.dumps(drift_report, indent=2)}

Structure your response as:
1. Severity: [LOW / MEDIUM / HIGH] — one sentence why
2. Key drifting features: list the top offenders with their values
3. Business impact: what could go wrong if ignored
4. Action: Retrain now / Monitor closely / No action needed — be specific"""

        context.add_message("user", prompt)
        response = await llm_service.chat_completion(
            context.get_messages(),
            system_prompt=context.system_prompt,
        )
        context.add_message("assistant", response)
        return response


class ModelComparator:
    """Compares different model versions."""

    async def compare_models(self, models: List[Dict[str, Any]], context: AIContext) -> str:
        if not models:
            return "No models provided for comparison."

        prompt = f"""Compare these {len(models)} model versions and recommend which to deploy.

{json.dumps(models, indent=2)}

Structure your response as:
1. Winner: [model name/version] — one sentence justification
2. Key differences: bullet points on the most important metric gaps
3. Trade-offs: any reasons you might NOT pick the winner (latency, stability, etc.)
4. Final recommendation: deploy / test further / keep current"""

        context.add_message("user", prompt)
        response = await llm_service.chat_completion(
            context.get_messages(),
            system_prompt=context.system_prompt,
        )
        context.add_message("assistant", response)
        return response


# Semaphore to allow only 1 Ollama inference at a time.
# This is the CPU fix — without this, concurrent requests pile up and
# each one fully saturates all cores simultaneously, freezing everything else.
_inference_lock = asyncio.Semaphore(1)


class MLOpsCopilot:
    """Main AI copilot orchestrating all capabilities."""

    def __init__(self):
        self.context = AIContext()
        self.fetcher = MLOpsDataFetcher()
        self.shap_explainer = SHAPExplainer()
        self.drift_analyzer = DriftAnalyzer()
        self.model_comparator = ModelComparator()

    async def chat(self, user_message: str) -> str:
        """
        General chat — routes intent, enriches with live data, serialises inference.
        """
        lower = user_message.lower()

        # Intent: drift + model name mentioned → auto-fetch live drift data
        if "drift" in lower:
            words = user_message.split()
            for i, word in enumerate(words):
                # BUG FIX: original checked words[i+1] without guarding i+1 < len
                # which raised IndexError on "tell me about drift" (last word = "drift")
                if word.lower() in ("model", "for") and i + 1 < len(words):
                    model_name = words[i + 1].strip("?.,")
                    drift_data = await self.fetcher.get_drift_report(model_name)
                    if drift_data:
                        enriched = (
                            f"{user_message}\n\nLive drift data:\n"
                            f"{json.dumps(drift_data, indent=2)}"
                        )
                        self.context.add_message("user", enriched)
                        async with _inference_lock:
                            response = await llm_service.chat_completion(
                                self.context.get_messages(),
                                system_prompt=self.context.system_prompt,
                            )
                        self.context.add_message("assistant", response)
                        return response

        # BUG FIX: original added user message to context BEFORE the drift branch,
        # meaning on a drift hit the message was added twice (once above, once in
        # the enriched block), doubling every drift-related user turn in history.
        # Now we add exactly once, in the right place.
        self.context.add_message("user", user_message)

        async with _inference_lock:
            response = await llm_service.chat_completion(
                self.context.get_messages(),
                system_prompt=self.context.system_prompt,
            )

        self.context.add_message("assistant", response)
        return response

    def reset_context(self):
        self.context.clear()


# Global instance
copilot = MLOpsCopilot()