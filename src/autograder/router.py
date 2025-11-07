from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query, status
from fastapi.responses import PlainTextResponse

from .schemas import (
    MessageResponse,
    RegisterRequest,
    RunInfo,
    RunResultResponse,
    ScheduleResponse,
    ScheduleRunRequest,
    StatsResponse,
    TeamSnapshot,
    TeamUpdateResponse,
    TeamUrlUpdate,
)
from .store import store


router = APIRouter(tags=["Autograder"])


def _normalize_phase(phase: str) -> str:
    normalized = phase.lower()
    if normalized not in store.phases:
        raise HTTPException(status_code=404, detail=f"Unknown phase '{phase}'")
    return normalized


@router.get("/phases", response_model=List[str], summary="List available phases")
async def list_phases() -> List[str]:
    return store.phases


@router.post(
    "/{phase}/register",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    summary="Register a team",
)
async def register_team(
    phase: str = Path(..., description="Autograder phase identifier."),
    payload: RegisterRequest = Body(...),
) -> MessageResponse:
    normalized_phase = _normalize_phase(phase)

    if normalized_phase in {"cli", "phase1"} and payload.github is None:
        raise HTTPException(
            status_code=400,
            detail="GitHub repository URL is required for CLI and Phase 1 registrations.",
        )

    if normalized_phase == "phase2":
        missing_fields = []
        if payload.endpoint is None:
            missing_fields.append("endpoint")
        if payload.fe_endpoint is None:
            missing_fields.append("fe_endpoint")
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field(s) for phase2 registration: {', '.join(missing_fields)}",
            )

    await store.register_team(normalized_phase, payload)
    return MessageResponse(message="Team registered successfully.")


@router.get(
    "/{phase}/schedule",
    summary="Get current scheduled runs",
    response_model=List[RunInfo],
)
async def get_schedule(phase: str = Path(..., description="Autograder phase identifier.")) -> List[RunInfo]:
    normalized_phase = _normalize_phase(phase)
    return await store.list_runs(normalized_phase)


@router.post(
    "/{phase}/schedule",
    status_code=status.HTTP_201_CREATED,
    response_model=ScheduleResponse,
    summary="Schedule a run",
)
async def schedule_run(
    phase: str = Path(..., description="Autograder phase identifier."),
    payload: ScheduleRunRequest = Body(...),
) -> ScheduleResponse:
    normalized_phase = _normalize_phase(phase)
    team = await store.get_team(normalized_phase, payload.group)
    if team is None:
        raise HTTPException(status_code=404, detail="Team is not registered for this phase.")
    run = await store.schedule_run(normalized_phase, payload.group)
    return ScheduleResponse(message="Run scheduled successfully.", run=run)


@router.get(
    "/{phase}/run/all",
    summary="Get currently running and scheduled runs",
    response_model=List[RunInfo],
)
async def get_run_all(phase: str = Path(..., description="Autograder phase identifier.")) -> List[RunInfo]:
    normalized_phase = _normalize_phase(phase)
    return await store.list_schedule(normalized_phase)


@router.delete(
    "/{phase}/run",
    summary="Cancel a run",
    response_model=MessageResponse,
)
async def cancel_run(
    phase: str = Path(..., description="Autograder phase identifier."),
    payload: ScheduleRunRequest = Body(...),
) -> MessageResponse:
    normalized_phase = _normalize_phase(phase)
    team = await store.get_team(normalized_phase, payload.group)
    if team is None:
        raise HTTPException(status_code=404, detail="Team is not registered for this phase.")
    removed = await store.cancel_run(normalized_phase, payload.group)
    if not removed:
        raise HTTPException(status_code=404, detail="No scheduled or running job found for this team.")
    return MessageResponse(message="Run cancelled successfully.")


async def _format_run_result(run: Optional[RunInfo]) -> RunResultResponse:
    if run is None:
        raise HTTPException(status_code=404, detail="No runs have been recorded for this team in the requested phase.")
    return RunResultResponse(
        group=run.group,
        phase=run.phase,
        status=run.status,
        score=run.score,
        logs=run.logs,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get(
    "/{phase}/last_run",
    summary="Check results from the last run",
    response_model=RunResultResponse,
)
async def get_last_run(
    phase: str = Path(..., description="Autograder phase identifier."),
    group: int = Query(..., ge=1, description="The group number."),
    gh_token: str = Query(..., description="GitHub authentication token."),
) -> RunResultResponse:
    normalized_phase = _normalize_phase(phase)
    team = await store.get_team(normalized_phase, group)
    if team is None or team.gh_token != gh_token:
        raise HTTPException(status_code=403, detail="Unauthorized.")
    run = await store.get_last_run(normalized_phase, group)
    return await _format_run_result(run)


@router.get(
    "/{phase}/best_run",
    summary="Check results from the best run",
    response_model=RunResultResponse,
)
async def get_best_run(
    phase: str = Path(..., description="Autograder phase identifier."),
    group: int = Query(..., ge=1, description="The group number."),
    gh_token: str = Query(..., description="GitHub authentication token."),
) -> RunResultResponse:
    normalized_phase = _normalize_phase(phase)
    team = await store.get_team(normalized_phase, group)
    if team is None or team.gh_token != gh_token:
        raise HTTPException(status_code=403, detail="Unauthorized.")
    run = await store.get_best_run(normalized_phase, group)
    return await _format_run_result(run)


@router.get(
    "/{phase}/log/download",
    summary="Download a log file",
    response_class=PlainTextResponse,
)
async def download_log(
    phase: str = Path(..., description="Autograder phase identifier."),
    group: int = Query(..., ge=1, description="The group number."),
    gh_token: str = Query(..., description="GitHub authentication token."),
    log: str = Query(..., description="Path of the log file."),
) -> PlainTextResponse:
    normalized_phase = _normalize_phase(phase)
    team = await store.get_team(normalized_phase, group)
    if team is None or team.gh_token != gh_token:
        raise HTTPException(status_code=403, detail="Unauthorized.")
    content = await store.get_logs(normalized_phase, group, log)
    if content is None:
        raise HTTPException(status_code=404, detail="Log file not found.")
    return PlainTextResponse(content, status_code=200)


@router.get(
    "/{phase}/stats",
    summary="Get current stats of the class",
    response_model=StatsResponse,
)
async def get_stats(phase: str = Path(..., description="Autograder phase identifier.")) -> StatsResponse:
    normalized_phase = _normalize_phase(phase)
    return await store.stats(normalized_phase)


@router.patch(
    "/{phase}/team/urls",
    summary="Update registered team URLs",
    response_model=TeamUpdateResponse,
)
async def update_team_urls(
    phase: str = Path(..., description="Autograder phase identifier."),
    payload: TeamUrlUpdate = Body(...),
) -> TeamUpdateResponse:
    normalized_phase = _normalize_phase(phase)
    team = await store.get_team(normalized_phase, payload.group)
    if team is None or team.gh_token != payload.gh_token:
        raise HTTPException(status_code=403, detail="Unauthorized.")

    updated = team.copy()
    if payload.github is not None:
        updated.github = payload.github
    if payload.endpoint is not None:
        updated.endpoint = payload.endpoint
    if payload.fe_endpoint is not None:
        updated.fe_endpoint = payload.fe_endpoint

    await store.register_team(normalized_phase, updated)
    snapshot = TeamSnapshot(
        github=updated.github,
        endpoint=updated.endpoint,
        fe_endpoint=updated.fe_endpoint,
        names=updated.names,
    )
    return TeamUpdateResponse(message="URLs updated successfully.", team=snapshot)


# Seed store with example data so endpoints have meaningful responses out of the box.
async def _seed_store() -> None:
    now = datetime.now(timezone.utc)
    sample = RegisterRequest(
        group=1,
        gh_token="sample-token",
        names=["Alice", "Bob"],
        github="https://github.com/example/autograder",
        endpoint="https://backend.example.com",
        fe_endpoint="https://frontend.example.com",
    )
    await store.register_team("phase2", sample)
    run = await store.schedule_run("phase2", 1)
    await store.start_run(run.run_id)
    await store.finish_run(
        run.run_id,
        score=95.5,
        logs="Run completed successfully.\nAll tests passed.",
        status="completed",
    )


# Schedule seeding once router is included
@router.on_event("startup")
async def _startup_seed() -> None:  # pragma: no cover - simple seed
    await _seed_store()

