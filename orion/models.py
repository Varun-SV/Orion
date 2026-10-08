from __future__ import annotations
from typing import Any, Generic, Protocol, TypeVar, Literal
from pydantic import BaseModel, ConfigDict, Field

KINDS = ('movies', 'series', 'anime', 'anime_films', 'web_series', 'music', 'books')
KIND_NAMES = dict(zip(KINDS, ('Movies', 'Series', 'Anime', 'Anime films', 'Web series', 'Music', 'Books')))
Kind = Literal['movies', 'series', 'anime', 'anime_films', 'web_series', 'music', 'books']
Status = Literal['pending', 'approved', 'organised', 'error', 'unavailable', 'no_match']

class Record(BaseModel):
    model_config = ConfigDict(extra='forbid')

class MatchDecision(Record):
    item_id: str
    provider: str = 'manual'
    provider_id: str = ''
    metadata: dict[str, Any]
    evidence: list[str] = Field(default_factory=list)

class MediaItem(Record):
    id: str
    source_id: str
    path: str
    kind: Kind
    status: Status = 'pending'
    signature: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    decision: MatchDecision | None = None

T = TypeVar('T')
class Page(Record, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int

class Candidate(Record):
    provider: str
    provider_id: str
    title: str
    year: str = ''
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)

class Operation(Record):
    id: str
    plan_id: str
    item_id: str
    kind: str = 'move'
    source: str
    destination: str
    expected_signature: dict[str, Any]
    state: str = 'pending'
    verification: dict[str, Any] = Field(default_factory=dict)

class PlanIssue(Record):
    code: str
    detail: str
    operation_id: str = ''
    item_id: str = ''

class OperationPlan(Record):
    id: str
    revision: int = 1
    operations: list[Operation] = Field(default_factory=list)
    issues: list[PlanIssue] = Field(default_factory=list)
    warnings: list[PlanIssue] = Field(default_factory=list)

class Job(Record):
    id: str
    kind: str
    state: str
    progress: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None

class JobContext(Protocol):
    def cancelled(self) -> bool: ...
    def progress(self, phase: str, items_done: int, items_total: int,
                 bytes_done: int = 0, bytes_total: int = 0) -> None: ...
