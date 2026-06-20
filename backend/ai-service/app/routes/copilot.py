from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import logging
import traceback

from app.services.copilot import copilot
from app.services.tools import COPILOT_TOOLS, tool_executor
from app.services.llm import LLMRateLimitError
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/copilot", tags=["copilot"])


class ChatRequest(BaseModel):
    message: str
    reset_context: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str
    context_length: int
    tools_used: List[str] = []


class ExplainSHAPRequest(BaseModel):
    shap_data: Dict[str, Any]
    model_name: Optional[str] = None


class DriftExplanationRequest(BaseModel):
    model_name: Optional[str] = None
    model_id: Optional[int] = None
    drift_data: Optional[Dict[str, Any]] = None


class ModelComparisonRequest(BaseModel):
    models: List[Dict[str, Any]]
    question: Optional[str] = None


class ToolInvokeRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}


def _rate_limit_detail(e: LLMRateLimitError) -> str:
    if e.retry_after and e.retry_after > 60:
        wait = f"{int(e.retry_after // 60)}m"
    else:
        wait = f"{int(e.retry_after or 5)}s"
    return f"AI service is at capacity. Try again in {wait}."


@router.post("/chat", response_model=ChatResponse)
async def chat_with_copilot(request: ChatRequest):
    """
    Chat with the MLOps Copilot using Groq function calling.

    The copilot can autonomously query MLflow, Prometheus, deployment-service,
    training-service, and monitoring metrics to answer questions about:
    - Experiments and training runs
    - Deployments and model schemas
    - Model performance and drift
    - Platform monitoring metrics
    """
    try:
        if request.reset_context:
            copilot.reset_context()

        response = await copilot.chat(request.message)

        return ChatResponse(
            response=response,
            context_length=len(copilot.context.get_messages()),
            tools_used=copilot.tools_used,
        )
    except LLMRateLimitError as e:
        logger.warning("Rate limit hit on /chat: %s", e)
        raise HTTPException(status_code=429, detail=_rate_limit_detail(e))
    except Exception as e:
        logger.error("Chat endpoint error: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def list_tools():
    """List all tools available to the copilot agent."""
    return {
        "count": len(COPILOT_TOOLS),
        "tools": [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "parameters": t["function"]["parameters"],
            }
            for t in COPILOT_TOOLS
        ],
    }


@router.post("/tools/invoke")
async def invoke_tool(request: ToolInvokeRequest):
    """Directly invoke a copilot tool (for debugging or programmatic access)."""
    result = await tool_executor.execute(request.tool_name, request.arguments)
    return {"tool": request.tool_name, "result": result}


@router.post("/explain-shap")
async def explain_shap(request: ExplainSHAPRequest):
    """Explain SHAP values in natural language."""
    try:
        explanation = await copilot.shap_explainer.explain_shap(
            request.shap_data,
            copilot.context,
        )
        return {"explanation": explanation, "model": request.model_name}
    except LLMRateLimitError as e:
        logger.warning("Rate limit hit on /explain-shap: %s", e)
        raise HTTPException(status_code=429, detail=_rate_limit_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain-drift")
async def explain_drift(request: DriftExplanationRequest):
    """Explain model drift — fetches live data when model_id is provided."""
    try:
        if not request.drift_data and request.model_id is not None:
            raw = await tool_executor.execute("get_model_drift", {"model_id": request.model_id})
            request.drift_data = json.loads(raw)

        if not request.drift_data:
            raise HTTPException(
                status_code=422,
                detail="Provide drift_data or model_id to fetch live drift report.",
            )

        explanation = await copilot.drift_analyzer.explain_drift(
            request.drift_data,
            copilot.context,
        )

        return {
            "model": request.model_name or request.model_id,
            "explanation": explanation,
            "drift_data": request.drift_data,
        }
    except HTTPException:
        raise
    except LLMRateLimitError as e:
        logger.warning("Rate limit hit on /explain-drift: %s", e)
        raise HTTPException(status_code=429, detail=_rate_limit_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare-models")
async def compare_models(request: ModelComparisonRequest):
    try:
        comparison = await copilot.model_comparator.compare_models(
            request.models,
            copilot.context,
        )
        return {"comparison": comparison, "models_compared": len(request.models)}
    except LLMRateLimitError as e:
        logger.warning("Rate limit hit on /compare-models: %s", e)
        raise HTTPException(status_code=429, detail=_rate_limit_detail(e))
    except Exception as e:
        logger.exception("Compare models failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.get("/context")
async def get_context():
    return {
        "messages": copilot.context.get_messages(),
        "message_count": len(copilot.context.get_messages()),
    }


@router.post("/reset-context")
async def reset_context():
    copilot.reset_context()
    return {"status": "context reset"}


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-service",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "tool_calling": True,
        "tools_available": len(COPILOT_TOOLS),
    }