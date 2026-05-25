"""
SAGE-PRO Chat & Correction API Routes
═══════════════════════════════════════
Handles correction submission and chat history retrieval.

Endpoints:
    POST /v1/correction — Submit a user correction
    GET  /v1/history    — Retrieve conversation history
"""

import os
import uuid
import structlog
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])


class CorrectionRequest(BaseModel):
    """Schema for submitting a user correction."""
    conversation_id: str = Field(..., description="UUID of the conversation")
    message_id: str = Field(..., description="UUID of the AI message being corrected")
    original_response: str = Field(..., description="The AI's wrong response")
    corrected_content: Optional[str] = Field(None, description="What the correct answer should be")
    user_message: str = Field("", description="The user's correction message text")
    thumbs_down: bool = Field(False, description="Whether the thumbs-down button was clicked")


class CorrectionResponse(BaseModel):
    """Response after processing a correction."""
    correction_id: str
    tier: str
    agents_penalised: List[str]
    penalty_applied: List[float]


@router.post("/v1/correction", response_model=CorrectionResponse)
async def submit_correction(req: CorrectionRequest, request: Request):
    """Processes a user correction through the penalty system.

    Flow:
        1. Detect correction tier (HARD/SOFT) via CorrectionDetector
        2. Apply penalty to responsible agents via AgentPenaltySystem
        3. Store correction in MistakeLibrary for future retrieval
        4. Log to RoutingLedger for daily batch processing
    """
    # Import v2 subsystems from the bootstrapped server globals
    from sage.api.server import _get_v2_subsystems

    subsystems = _get_v2_subsystems()
    if subsystems is None:
        raise HTTPException(status_code=503, detail="V2 subsystems not yet initialized")

    detector = subsystems["correction_detector"]
    penalty_system = subsystems["penalty_system"]
    mistake_library = subsystems.get("mistake_library")
    routing_ledger = subsystems["routing_ledger"]

    # 1. Detect correction tier
    tier = detector.detect(
        user_message=req.user_message,
        thumbs_down=req.thumbs_down,
    )

    if tier.value == "none":
        return CorrectionResponse(
            correction_id=str(uuid.uuid4()),
            tier="none",
            agents_penalised=[],
            penalty_applied=[],
        )

    # 2. Apply penalty to all agents (in production, identify responsible agents)
    responsible_agents = ["architect", "implementer", "synthesizer", "red_team"]
    penalties = []

    for agent_name in responsible_agents:
        # Retrieve current weight (default 1.0 — in production from DB)
        current_weight = 1.0
        current_epsilon = 0.15

        if tier.value == "hard":
            new_w, new_eps = penalty_system.apply_hard_penalty(current_weight, current_epsilon)
        else:
            new_w, new_eps = penalty_system.apply_soft_penalty(current_weight, current_epsilon)

        penalties.append(round(current_weight - new_w, 4))

    # 3. Store in Mistake Library
    correction_id = str(uuid.uuid4())
    if mistake_library is not None:
        try:
            mistake_library.store(
                mistake_id=correction_id,
                original_response=req.original_response,
                corrected_content=req.corrected_content or "",
                query_text=req.user_message,
                user_id="anonymous",  # In production, extract from JWT
                responsible_agents=responsible_agents,
            )
        except Exception as e:
            logger.warning("mistake_library_store_failed", error=str(e))

    # 4. Annotate routing ledger
    # (In production, match to the specific routing entry by conversation_id)

    logger.info(
        "correction_processed",
        correction_id=correction_id,
        tier=tier.value,
        agents=responsible_agents,
        penalties=penalties,
    )

    return CorrectionResponse(
        correction_id=correction_id,
        tier=tier.value,
        agents_penalised=responsible_agents,
        penalty_applied=penalties,
    )


@router.get("/v1/history")
async def get_history(conversation_id: Optional[str] = None, limit: int = 50):
    """Retrieves conversation history.

    In production, reads from PostgreSQL via the chat_history_store.
    Currently returns a placeholder acknowledging the endpoint is live.
    """
    return {
        "status": "ready",
        "conversation_id": conversation_id,
        "messages": [],
        "note": "Full PostgreSQL integration pending deployment",
    }
