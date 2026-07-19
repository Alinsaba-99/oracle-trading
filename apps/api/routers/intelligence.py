"""Read-only gateway for external intelligence agents such as ElizaOS."""

from pathlib import Path

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from apps.api.config import APISettings
from apps.api.services.intelligence_service import SQLiteIntelligenceInbox
from core.domain.intelligence import OpportunityObservation

router = APIRouter(prefix="/intelligence", tags=["intelligence"])
settings = APISettings()
inbox = SQLiteIntelligenceInbox(Path(settings.data_dir) / "intelligence.db")


@router.post("/observations", status_code=status.HTTP_202_ACCEPTED)
async def receive_observation(observation: OpportunityObservation) -> JSONResponse:
    """Validate and durably store an observation; never execute it directly."""
    created = await inbox.save(observation)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "observation_id": observation.observation_id,
            "accepted": True,
            "duplicate": not created,
            "execution_access": False,
        },
    )
