from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator

from core.knowledge_sync.models import FetchedItem, SyncSourceConfig, SyncState
from core.knowledge_sync.source_base import SyncSource

_MAX_TRANSCRIPT_CHARS = 15_000


class YoutubeSyncSource(SyncSource):
    def __init__(self, config: SyncSourceConfig) -> None:
        super().__init__(config)

    @staticmethod
    def _extract_video_id(uri: str) -> str | None:
        patterns = [
            r"(?:youtube\.com/watch\?v=)([\w-]+)",
            r"(?:youtu\.be/)([\w-]+)",
            r"(?:youtube\.com/embed/)([\w-]+)",
        ]
        for pat in patterns:
            m = re.search(pat, uri)
            if m:
                return m.group(1)
        return None

    async def fetch(self, state: SyncState) -> AsyncIterator[FetchedItem]:
        video_id = self._extract_video_id(self._config.uri)
        if not video_id:
            return

        if video_id in state.seen_urls:
            return
        state.seen_urls.add(video_id)

        transcript = await self._fetch_transcript(video_id)
        if not transcript:
            return

        title = self._config.label or f"YouTube: {video_id}"
        content = f"Title: {title}\n\nTranscript:\n{transcript}"[:_MAX_TRANSCRIPT_CHARS]

        yield FetchedItem(
            url=f"https://www.youtube.com/watch?v={video_id}",
            title=title,
            content=content,
            summary=transcript[:500],
            metadata={"source": "youtube", "video_id": video_id},
        )

    async def _fetch_transcript(self, video_id: str) -> str | None:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            transcript_list = await asyncio.to_thread(YouTubeTranscriptApi.get_transcript, video_id)
            if transcript_list:
                return " ".join(item.get("text", "") for item in transcript_list)
            return None
        except Exception:
            return None

    async def validate(self) -> str | None:
        video_id = self._extract_video_id(self._config.uri)
        if not video_id:
            return "Invalid YouTube URL"
        transcript = await self._fetch_transcript(video_id)
        if transcript is None:
            return "Could not fetch transcript (no captions available)"
        return None

    async def estimate_next(self) -> int:
        return 1
