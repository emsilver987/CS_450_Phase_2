from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class RegisterRequest(BaseModel):
    group: int = Field(..., ge=1)
    gh_token: str = Field(..., min_length=1)
    names: List[str] = Field(..., min_items=1)
    github: Optional[HttpUrl] = None
    endpoint: Optional[HttpUrl] = None
    fe_endpoint: Optional[HttpUrl] = None


class ScheduleRunRequest(BaseModel):
    group: int = Field(..., ge=1)
    gh_token: str = Field(..., min_length=1)


class TeamUrlUpdate(BaseModel):
    group: int = Field(..., ge=1)
    gh_token: str = Field(..., min_length=1)
    github: Optional[HttpUrl] = None
    endpoint: Optional[HttpUrl] = None
    fe_endpoint: Optional[HttpUrl] = None


class MessageResponse(BaseModel):
    message: str


class TeamSnapshot(BaseModel):
    github: Optional[HttpUrl] = None
    endpoint: Optional[HttpUrl] = None
    fe_endpoint: Optional[HttpUrl] = None
    names: List[str] = Field(default_factory=list)


class TeamUpdateResponse(BaseModel):
    message: str
    team: TeamSnapshot


class RunInfo(BaseModel):
    run_id: str
    group: int
    phase: str
    status: str
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    score: Optional[float] = None
    logs: Optional[str] = None


class StatsResponse(BaseModel):
    average: float
    maximum: float
    median: float
    minimum: float
    standard_deviation: float


class LogDownloadResponse(BaseModel):
    group: int
    log: str
    phase: str
    content: str


class RunResultResponse(BaseModel):
    group: int
    phase: str
    status: str
    score: Optional[float] = None
    logs: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class PhaseRunsResponse(BaseModel):
    runs: List[RunInfo]


class ScheduleResponse(BaseModel):
    message: str
    run: RunInfo


class StatsMap(BaseModel):
    phase: str
    stats: StatsResponse
    sample_size: int
    results: List[Dict[str, str]]

