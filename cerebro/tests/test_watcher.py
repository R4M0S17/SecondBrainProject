import asyncio
from unittest.mock import MagicMock, patch

import pytest
from watchdog.events import FileModifiedEvent

import core.watcher.file_watcher as fw_module
from core.watcher.file_watcher import FileWatcher


@pytest.fixture
def queue():
    return asyncio.Queue()


@pytest.fixture
def watcher(queue):
    return FileWatcher(paths=["/tmp/watched"], ingestion_queue=queue)


class TestDebounce:
    async def test_rapid_events_produce_single_queue_entry(self, watcher, queue):
        """Multiple rapid events for the same file collapse into one queue entry."""
        watcher._loop = asyncio.get_event_loop()
        original = fw_module.DEBOUNCE_SECONDS
        fw_module.DEBOUNCE_SECONDS = 0.05
        try:
            for _ in range(5):
                watcher._schedule_debounce("/tmp/watched/notes.md")
            await asyncio.sleep(0.2)
        finally:
            fw_module.DEBOUNCE_SECONDS = original

        assert queue.qsize() == 1
        assert await queue.get() == "/tmp/watched/notes.md"

    async def test_distinct_files_debounce_independently(self, watcher, queue):
        """Each filepath has its own debounce timer."""
        watcher._loop = asyncio.get_event_loop()
        original = fw_module.DEBOUNCE_SECONDS
        fw_module.DEBOUNCE_SECONDS = 0.05
        try:
            watcher._schedule_debounce("/tmp/watched/a.txt")
            watcher._schedule_debounce("/tmp/watched/b.txt")
            await asyncio.sleep(0.2)
        finally:
            fw_module.DEBOUNCE_SECONDS = original

        assert queue.qsize() == 2

    async def test_timer_cancelled_on_rapid_repeat(self, watcher, queue):
        """Only the last event fires; intermediate timers are cancelled."""
        watcher._loop = asyncio.get_event_loop()
        original = fw_module.DEBOUNCE_SECONDS
        fw_module.DEBOUNCE_SECONDS = 0.1
        try:
            watcher._schedule_debounce("/tmp/watched/doc.py")
            await asyncio.sleep(0.05)  # not yet expired
            watcher._schedule_debounce("/tmp/watched/doc.py")  # resets timer
            await asyncio.sleep(0.05)  # still not expired from second call
            assert queue.qsize() == 0  # should not have fired yet
            await asyncio.sleep(0.1)  # now it should fire
        finally:
            fw_module.DEBOUNCE_SECONDS = original

        assert queue.qsize() == 1


class TestIgnoreFilters:
    def test_dotfiles_are_ignored(self, watcher):
        assert watcher._should_ignore("/tmp/watched/.hidden")
        assert watcher._should_ignore("/tmp/watched/.DS_Store")

    def test_ignored_dirs_are_ignored(self, watcher):
        assert watcher._should_ignore("/tmp/watched/.git/config")
        assert watcher._should_ignore("/tmp/watched/node_modules/pkg/index.js")
        assert watcher._should_ignore("/tmp/watched/__pycache__/foo.pyc")
        assert watcher._should_ignore("/tmp/watched/.venv/lib/site.py")

    def test_swap_and_tmp_files_are_ignored(self, watcher):
        assert watcher._should_ignore("/tmp/watched/notes.md.swp")
        assert watcher._should_ignore("/tmp/watched/draft.tmp")
        assert watcher._should_ignore("/tmp/watched/file.txt~")

    def test_unsupported_extensions_are_ignored(self, watcher):
        assert watcher._should_ignore("/tmp/watched/image.png")
        assert watcher._should_ignore("/tmp/watched/data.csv")
        assert watcher._should_ignore("/tmp/watched/binary.exe")

    def test_supported_extensions_are_not_ignored(self, watcher):
        for ext in [".pdf", ".txt", ".md", ".py", ".docx"]:
            assert not watcher._should_ignore(f"/tmp/watched/file{ext}")

    def test_ignored_file_never_reaches_queue(self, watcher, queue):
        """_on_modified with an ignored file leaves the queue empty."""
        watcher._loop = MagicMock()

        for path in [
            "/tmp/watched/image.png",
            "/tmp/watched/.hidden.md",
            "/tmp/watched/notes.md.swp",
            "/tmp/watched/__pycache__/mod.pyc",
        ]:
            event = FileModifiedEvent(path)
            watcher._on_modified(event)

        assert queue.qsize() == 0
        watcher._loop.call_soon_threadsafe.assert_not_called()

    def test_valid_file_reaches_call_soon_threadsafe(self, watcher):
        """_on_modified with a valid file calls call_soon_threadsafe."""
        mock_loop = MagicMock()
        watcher._loop = mock_loop

        event = FileModifiedEvent("/tmp/watched/report.pdf")
        watcher._on_modified(event)

        mock_loop.call_soon_threadsafe.assert_called_once()


class TestStartStop:
    def test_start_stop_cycle_is_clean(self, watcher):
        """start() then stop() runs without error and cleans up state."""
        mock_observer = MagicMock()
        watcher._observer = mock_observer

        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            watcher.start()

        assert watcher._loop is mock_loop
        mock_observer.schedule.assert_called_once_with(
            watcher._handler, "/tmp/watched", recursive=True
        )
        mock_observer.start.assert_called_once()

        watcher.stop()
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()
        assert watcher._timers == {}

    def test_stop_cancels_pending_timers(self, watcher):
        """stop() cancels all in-flight debounce timers."""
        handle_a = MagicMock()
        handle_b = MagicMock()
        watcher._timers = {"/tmp/a.md": handle_a, "/tmp/b.txt": handle_b}

        mock_observer = MagicMock()
        watcher._observer = mock_observer
        watcher.stop()

        handle_a.cancel.assert_called_once()
        handle_b.cancel.assert_called_once()
        assert watcher._timers == {}

    def test_multiple_paths_all_scheduled(self, queue):
        """start() schedules each watched path with the observer."""
        paths = ["/tmp/dir1", "/tmp/dir2", "/tmp/dir3"]
        w = FileWatcher(paths=paths, ingestion_queue=queue)
        mock_observer = MagicMock()
        w._observer = mock_observer

        with patch("asyncio.get_event_loop", return_value=MagicMock()):
            w.start()

        assert mock_observer.schedule.call_count == 3
        scheduled_paths = [c.args[1] for c in mock_observer.schedule.call_args_list]
        assert set(scheduled_paths) == set(paths)
