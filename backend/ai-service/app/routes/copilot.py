from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import logging
import traceback

from app.services.copilot import copilot
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/copilot", tags=["copilot"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    reset_context: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str
    context_length: int


class ExplainSHAPRequest(BaseModel):
    shap_data: Dict[str, Any]
    model_name: Optional[str] = None


class DriftExplanationRequest(BaseModel):
    model_name: str
    drift_data: Optional[Dict[str, Any]] = None


class ModelComparisonRequest(BaseModel):
    models: List[Dict[str, Any]]
    question: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_copilot(request: ChatRequest):
    """
    Chat with the AI copilot.
    
    The copilot maintains conversation context and can answer questions about:
    - SHAP explanations
    - Model drift analysis
    - Model comparisons
    - General MLOps guidance
    """
    try:
        if request.reset_context:
            copilot.reset_context()
        
        response = await copilot.chat(request.message)
        
        return ChatResponse(
            response=response,
            context_length=len(copilot.context.get_messages())
        )
    except Exception as e:
        logger.error(f"Chat endpoint error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain-shap")
async def explain_shap(request: ExplainSHAPRequest):
    """
    Explain SHAP values in natural language.
    
    Provide SHAP data (base_value, values, features) and get
    a business-friendly explanation of what the model is doing.
    """
    try:
        explanation = await copilot.shap_explainer.explain_shap(
            request.shap_data,
            copilot.context
        )
        
        return {
            "explanation": explanation,
            "model": request.model_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain-drift")
async def explain_drift(request: DriftExplanationRequest):
    """
    Explain model drift in detail.
    
    Provides analysis of:
    - Severity of drift
    - Which features are drifting
    - Impact on model performance
    - Recommended actions
    """
    try:
        # If drift_data not provided, fetch from monitoring service
        if not request.drift_data:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{settings.MONITORING_SERVICE_URL}/drift/{request.model_name}",
                        timeout=10.0
                    )
                    response.raise_for_status()
                    request.drift_data = response.json()
            except Exception as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"Could not fetch drift data: {str(e)}"
                )
        
        explanation = await copilot.drift_analyzer.explain_drift(
            request.drift_data,
            copilot.context
        )
        
        return {
            "model": request.model_name,
            "explanation": explanation,
            "drift_data": request.drift_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare-models")
async def compare_models(request: ModelComparisonRequest):
    try:
        logger.info(f"REQUEST = {request.model_dump()}")

        comparison = await copilot.model_comparator.compare_models(
            request.models,
            copilot.context
        )

        logger.info("COMPARE SUCCESS")

        return {
            "comparison": comparison,
            "models_compared": len(request.models)
        }

    except Exception as e:
        logger.exception("COMPARE FAILED")
        
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {e}"
        )


@router.get("/context")
async def get_context():
    """Get current conversation context."""
    return {
        "messages": copilot.context.get_messages(),
        "message_count": len(copilot.context.get_messages())
    }


@router.post("/reset-context")
async def reset_context():
    """Reset conversation context."""
    copilot.reset_context()
    return {"status": "context reset"}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ai-service",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL
    }