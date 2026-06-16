from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SourceType(StrEnum):
    RSS = "rss"
    GITHUB = "github"
    WEB = "web"
    MANUAL = "manual"
    ARXIV = "arxiv"
    YOUTUBE = "youtube"
    PUBMED = "pubmed"


class SyncStatus(StrEnum):
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"


@dataclass
class SyncSourceConfig:
    id: str
    source_type: SourceType
    uri: str
    label: str = ""
    enabled: bool = True
    interval_minutes: int = 60
    max_items_per_sync: int = 20
    filter_min_relevance: float = 0.3
    tags: list[str] = field(default_factory=list)
    schedule_cron: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class SyncState:
    source_id: str
    status: SyncStatus = SyncStatus.IDLE
    last_sync_at: float = 0.0
    last_sync_duration_ms: float = 0.0
    last_error: str = ""
    etag: str = ""
    last_modified: str = ""
    items_fetched_count: int = 0
    items_indexed_count: int = 0
    consecutive_errors: int = 0
    seen_urls: set[str] = field(default_factory=set)


@dataclass
class SyncResult:
    source_id: str
    fetched: int
    filtered_out: int
    indexed: int
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class FetchedItem:
    url: str
    title: str
    content: str
    summary: str = ""
    author: str = ""
    published_at: float = 0.0
    language: str = "unknown"
    metadata: dict = field(default_factory=dict)
