"""
Oversight Configuration API.
"""
from fastapi import APIRouter, Request

from app.dependencies import SessionDep, ActorDep
from app.schemas.oversight import OversightConfigUpdate, OversightBulkUpdate, OversightConfigOut
from app.services import oversight_service, audit_service
from app.models.audit_log import ActorType

router = APIRouter()


@router.get("/config", response_model=list[OversightConfigOut])
async def get_all_configs(db: SessionDep):
    configs = await oversight_service.get_all_configs(db)
    return configs


@router.put("/config/system", response_model=OversightConfigOut)
async def update_system_config(
    body: OversightConfigUpdate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    config = await oversight_service.upsert_system_config(
        db,
        mode=body.mode,
        confidence_threshold=body.confidence_threshold,
        updated_by=actor,
    )
    await audit_service.log_event(
        db,
        entity_type="OversightConfig",
        entity_id=config.id,
        action="oversight_toggle",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        after_state={"scope": "SYSTEM", "mode": body.mode},
        ip_address=request.client.host if request.client else None,
    )
    return config


@router.put("/config/stages/{stage}", response_model=OversightConfigOut)
async def update_stage_config(
    stage: str,
    body: OversightConfigUpdate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    from app.models.daca_request import DacaRequestStatus
    from fastapi import HTTPException

    # Cannot override always-human stages
    if stage in DacaRequestStatus.ALWAYS_HUMAN:
        raise HTTPException(
            status_code=422,
            detail=f"Stage '{stage}' always requires human approval and cannot be automated.",
        )

    config = await oversight_service.upsert_stage_config(
        db,
        stage=stage,
        mode=body.mode,
        confidence_threshold=body.confidence_threshold,
        updated_by=actor,
    )
    await audit_service.log_event(
        db,
        entity_type="OversightConfig",
        entity_id=config.id,
        action="oversight_toggle",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        after_state={"scope": "STAGE", "stage": stage, "mode": body.mode},
        ip_address=request.client.host if request.client else None,
    )
    return config


@router.post("/config/bulk", response_model=list[OversightConfigOut])
async def bulk_update_configs(
    body: OversightBulkUpdate,
    db: SessionDep,
    actor: ActorDep,
):
    from app.models.daca_request import DacaRequestStatus

    results = []
    for update in body.updates:
        stage = update.get("stage")
        mode = update.get("mode")
        threshold = update.get("confidence_threshold", 0.85)

        if stage and stage in DacaRequestStatus.ALWAYS_HUMAN:
            continue  # silently skip always-human stages

        if stage:
            config = await oversight_service.upsert_stage_config(
                db, stage=stage, mode=mode, confidence_threshold=threshold,
                updated_by=actor,
            )
        else:
            config = await oversight_service.upsert_system_config(
                db, mode=mode, confidence_threshold=threshold, updated_by=actor,
            )
        results.append(config)
    return results
