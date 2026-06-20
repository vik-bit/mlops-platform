import json
import logging
from typing import List, Dict, Any, Optional

from app.services.llm import llm_service, parse_tool_arguments
from app.services.tools import COPILOT_TOOLS, tool_executor
from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an MLOps Copilot embedded in an ML platform. You help data scientists and ML engineers with experiments, deployments, model performance, and monitoring metrics.

You have tools to query live platform data:
- MLflow: experiments, training runs, metrics, and parameters
- Prometheus: platform metrics (CPU, memory, request counts) and custom PromQL queries
- Deployment service: active deployments and model input schemas
- Training service: training jobs, model registry, job comparisons, feature importance
- Monitoring: prediction stats, drift detection, prediction history

Rules:
- Use tools proactively when the user asks about experiments, deployments, models, metrics, drift, or performance.
- Always call the relevant tool before answering factual questions about platform state.
- Be concise. Lead with the answer, then explain.
- When given JSON data, reference actual numbers (accuracy, latency, drift scores).
- For drift: state severity (low/medium/high) first, then detail drifting features.
- For model comparison: name a winner and justify in one sentence.
- Model IDs are integers from the model registry. Training job IDs are separate integers.
- If a tool returns an error, explain what failed and suggest next steps.
- Never say "I cannot" — give a best-effort answer with available data."""


class AIContext:
    """Maintains conversation context with a sliding window to avoid token overload."""

    def __init__(self, max_messages: int = None):
        self.messages: List[Dict[str, Any]] = []
        self.max_messages = max_messages or settings.LLM_MAX_CONTEXT_MESSAGES
        self.system_prompt = SYSTEM_PROMPT

    def add_message(self, role: str, content: str, **extra: Any):
        msg: Dict[str, Any] = {"role": role, "content": content}
        msg.update(extra)
        self.messages.append(msg)
        while len(self.messages) > self.max_messages:
            self.messages = self.messages[2:]

    def extend_messages(self, new_messages: List[Dict[str, Any]]):
        """Append several raw messages at once (e.g. assistant tool_calls + tool results),
        keeping the same trim behaviour as add_message."""
        self.messages.extend(new_messages)
        while len(self.messages) > self.max_messages:
            self.messages = self.messages[2:]

    def get_messages(self) -> List[Dict[str, Any]]:
        return self.messages.copy()

    def clear(self):
        self.messages = []


class SHAPExplainer:
    """Explains SHAP outputs in natural language."""

    async def explain_shap(self, shap_data: Dict[str, Any], context: AIContext) -> str:
        if not shap_data or "values" not in shap_data:
            return (
                "No SHAP data provided. Pass base_value, values (feature→contribution dict), "
                "and optionally feature names."
            )

        values = shap_data.get("values", {})
        if isinstance(values, list):
            feature_names = shap_data.get(
                "feature_names", [f"feature_{i}" for i in range(len(values))]
            )
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
            return "No drift report available. Provide drift metrics or a model_id to fetch live data."

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


class MLOpsCopilot:
    """MLOps Copilot with Groq-powered function calling."""

    def __init__(self):
        self.context = AIContext()
        self.shap_explainer = SHAPExplainer()
        self.drift_analyzer = DriftAnalyzer()
        self.model_comparator = ModelComparator()
        self.tools_used: List[str] = []

    async def chat(self, user_message: str) -> str:
        """Run the agent loop: LLM decides which tools to call, then synthesizes an answer."""
        self.tools_used = []
        self.context.add_message("user", user_message)

        # working_messages starts as a copy of context, but every message we
        # add during the loop (assistant tool_calls + tool results) is also
        # mirrored into self.context via extend_messages below, so follow-up
        # questions can still reference earlier tool results.
        working_messages = self.context.get_messages()
        pending: List[Dict[str, Any]] = []
        final_response = ""

        for iteration in range(settings.LLM_MAX_TOOL_ITERATIONS):
            result = await llm_service.chat_completion_with_tools(
                messages=working_messages,
                tools=COPILOT_TOOLS,
                system_prompt=self.context.system_prompt,
            )

            tool_calls = result.get("tool_calls")
            if tool_calls:
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": result.get("content") or "",
                    "tool_calls": tool_calls,
                }
                working_messages.append(assistant_msg)
                pending.append(assistant_msg)

                for call in tool_calls:
                    fn = call.get("function", {})
                    tool_name = fn.get("name", "")
                    args = parse_tool_arguments(fn.get("arguments", "{}"))
                    logger.info("Tool call [%d]: %s(%s)", iteration + 1, tool_name, args)

                    tool_result = await tool_executor.execute(tool_name, args)
                    self.tools_used.append(tool_name)

                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": call.get("id", tool_name),
                        "content": tool_result,
                    }
                    working_messages.append(tool_msg)
                    pending.append(tool_msg)
                continue

            final_response = (result.get("content") or "").strip()
            if not final_response:
                final_response = "I couldn't generate a response. Please try rephrasing your question."
            break
        else:
            final_response = (
                final_response
                or "I reached the maximum number of tool calls. Here's what I found so far — please ask a follow-up."
            )

        # Persist the full exchange — every tool_calls/tool message generated
        # during the loop — into the durable context, not just the final
        # answer. Without this, the tool results vanish as soon as chat()
        # returns and follow-up questions can't reference them.
        if pending:
            self.context.extend_messages(pending)
        self.context.add_message("assistant", final_response)
        return final_response

    def reset_context(self):
        self.context.clear()
        self.tools_used = []


copilot = MLOpsCopilot()