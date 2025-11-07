from __future__ import annotations

import asyncio
import statistics
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .schemas import RegisterRequest, RunInfo, StatsResponse


class AutograderStore:
    """Simple in-memory store backing the Autograder API."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._phases: List[str] = ["cli", "phase1", "phase2"]
        self._teams: Dict[Tuple[str, int], RegisterRequest] = {}
        self._scheduled_runs: Dict[str, RunInfo] = {}
        self._results: Dict[Tuple[str, int], List[RunInfo]] = {}
        self._logs: Dict[str, str] = {}

    @property
    def phases(self) -> List[str]:
        return list(self._phases)

    async def register_team(self, phase: str, payload: RegisterRequest) -> RegisterRequest:
        async with self._lock:
            key = (phase, payload.group)
            self._teams[key] = payload
            return payload

    async def get_team(self, phase: str, group: int) -> [RegisterRequest]:
        async with self._lock:
            return self._teams.get((phase, group))

    async def list_schedule(self, phase: str) -> List[RunInfo]:
        async with self._lock:
            return [run for run in self._scheduled_runs.values() if run.phase == phase]

    async def list_runs(self, phase: str) -> List[RunInfo]:
        async with self._lock:
            runs = [run for run in self._scheduled_runs.values() if run.phase == phase]
            completed: List[RunInfo] = []
            for (key_phase, _), results in self._results.items():
                if key_phase == phase:
                    completed.extend(results)
            return runs + completed

    async def schedule_run(self, phase: str, group: int) -> RunInfo:
        async with self._lock:
            run_id = str(uuid.uuid4())
            run = RunInfo(
                run_id=run_id,
                phase=phase,
                group=group,
                status="scheduled",
                scheduled_at=datetime.now(timezone.utc),
            )
            self._scheduled_runs[run_id] = run
            return run

    async def cancel_run(self, phase: str, group: int) -> bool:
        async with self._lock:
            for run_id, run in list(self._scheduled_runs.items()):
                if run.phase == phase and run.group == group:
                    del self._scheduled_runs[run_id]
                    return True
            return False

    async def start_run(self, run_id: str) -> None:
        async with self._lock:
            run = self._scheduled_runs.get(run_id)
            if run:
                run.status = "running"
                run.started_at = datetime.now(timezone.utc)

    async def finish_run(
        self,
        run_id: str,
        score: float,
        logs: Optional[str] = None,
        status: str = "completed",
    ) -> Optional[RunInfo]:
        async with self._lock:
            run = self._scheduled_runs.pop(run_id, None)
            if not run:
                return None
            run.status = status
            run.score = score
            run.logs = logs
            run.finished_at = datetime.now(timezone.utc)
            key = (run.phase, run.group)
            self._results.setdefault(key, []).append(run)
            if logs:
                log_key = self._log_key(run.phase, run.group)
                self._logs[log_key] = logs
            return run

    async def get_last_run(self, phase: str, group: int) -> Optional[RunInfo]:
        async with self._lock:
            runs = self._results.get((phase, group), [])
            return runs[-1] if runs else None

    async def get_best_run(self, phase: str, group: int) -> Optional[RunInfo]:
        async with self._lock:
            runs = self._results.get((phase, group), [])
            if not runs:
                return None
            scored = [run for run in runs if run.score is not None]
            if not scored:
                return runs[-1]
            return max(scored, key=lambda r: r.score or 0.0)

    async def get_logs(self, phase: str, group: int, log_path: str) -> Optional[str]:
        async with self._lock:
            return self._logs.get(self._log_key(phase, group), f"No logs found for {log_path}")

    async def stats(self, phase: str) -> StatsResponse:
        async with self._lock:
            scores: List[float] = []
            for key, results in self._results.items():
                key_phase, _ = key
                if key_phase != phase:
                    continue
                for run in results:
                    if run.score is not None:
                        scores.append(run.score)
            if not scores:
                return StatsResponse(
                    average=0.0, maximum=0.0, median=0.0, minimum=0.0, standard_deviation=0.0
                )
            avg = sum(scores) / len(scores)
            maximum = max(scores)
            minimum = min(scores)
            median = statistics.median(scores)
            stdev = statistics.pstdev(scores) if len(scores) > 1 else 0.0
            return StatsResponse(
                average=round(avg, 2),
                maximum=round(maximum, 2),
                median=round(median, 2),
                minimum=round(minimum, 2),
                standard_deviation=round(stdev, 2),
            )

    def _log_key(self, phase: str, group: int) -> str:
        return f"{phase}:{group}"


store = AutograderStore()

