from unittest.mock import MagicMock, patch

import pytest

from core.inference.fleet.hardware_monitor import HardwareSnapshot, snapshot


class TestHardwareSnapshot:
    """Tests for HardwareSnapshot dataclass."""

    def test_snapshot_returns_dataclass(self):
        """Verify snapshot() returns a populated HardwareSnapshot."""
        hw = snapshot()
        assert isinstance(hw, HardwareSnapshot)
        assert hw.ram_total_gb > 0
        assert hw.ram_available_gb > 0
        assert hw.cpu_count > 0
        assert hw.cpu_percent >= 0
        assert hw.gpu_backend in ("metal", "cuda", "none")

    def test_snapshot_fields_are_valid(self):
        """Verify snapshot fields have valid ranges."""
        hw = snapshot()
        assert 0 < hw.ram_available_gb <= hw.ram_total_gb
        assert 0 <= hw.cpu_percent <= 100
        assert hw.cpu_count >= 1
        assert hw.gpu_vram_total_gb >= 0
        assert hw.gpu_vram_available_gb >= 0
        assert hw.unified_memory in (True, False)

    @patch("core.inference.fleet.hardware_monitor.platform.processor")
    @patch("core.inference.fleet.hardware_monitor.psutil.virtual_memory")
    @patch("core.inference.fleet.hardware_monitor.psutil.cpu_count")
    @patch("core.inference.fleet.hardware_monitor.psutil.cpu_percent")
    def test_apple_silicon_unified_memory(
        self, mock_cpu_percent, mock_cpu_count, mock_vm, mock_processor
    ):
        """Verify Apple Silicon detection sets unified_memory=True and vram=ram."""
        mock_processor.return_value = "arm64"
        mock_cpu_count.return_value = 8
        mock_cpu_percent.return_value = 50.0
        mock_vm.return_value = MagicMock(
            total=16 * (1024**3),
            available=8 * (1024**3),
        )

        hw = snapshot()
        assert hw.gpu_backend == "metal"
        assert hw.unified_memory is True
        assert hw.gpu_vram_total_gb == hw.ram_total_gb
        assert hw.gpu_vram_available_gb == hw.ram_available_gb

    @patch("core.inference.fleet.hardware_monitor.subprocess.run")
    @patch("core.inference.fleet.hardware_monitor.platform.processor")
    @patch("core.inference.fleet.hardware_monitor.psutil.virtual_memory")
    @patch("core.inference.fleet.hardware_monitor.psutil.cpu_count")
    @patch("core.inference.fleet.hardware_monitor.psutil.cpu_percent")
    def test_nvidia_gpu_detected(
        self, mock_cpu_percent, mock_cpu_count, mock_vm, mock_processor, mock_run
    ):
        """Verify NVIDIA GPU detection via nvidia-smi."""
        mock_processor.return_value = "x86_64"
        mock_cpu_count.return_value = 4
        mock_cpu_percent.return_value = 25.0
        mock_vm.return_value = MagicMock(
            total=16 * (1024**3),
            available=8 * (1024**3),
        )
        # nvidia-smi output: total=24576 MB, free=12288 MB
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="24576,12288\n",
        )

        hw = snapshot()
        assert hw.gpu_backend == "cuda"
        assert hw.gpu_vram_total_gb == pytest.approx(24.0, rel=0.1)
        assert hw.gpu_vram_available_gb == pytest.approx(12.0, rel=0.1)
        assert hw.unified_memory is False

    @patch("core.inference.fleet.hardware_monitor.subprocess.run")
    @patch("core.inference.fleet.hardware_monitor.platform.processor")
    @patch("core.inference.fleet.hardware_monitor.psutil.virtual_memory")
    @patch("core.inference.fleet.hardware_monitor.psutil.cpu_count")
    @patch("core.inference.fleet.hardware_monitor.psutil.cpu_percent")
    def test_no_gpu_fallback(
        self, mock_cpu_percent, mock_cpu_count, mock_vm, mock_processor, mock_run
    ):
        """Verify graceful fallback when no GPU is detected."""
        mock_processor.return_value = "x86_64"
        mock_cpu_count.return_value = 4
        mock_cpu_percent.return_value = 25.0
        mock_vm.return_value = MagicMock(
            total=16 * (1024**3),
            available=8 * (1024**3),
        )
        # nvidia-smi fails
        mock_run.side_effect = FileNotFoundError()

        hw = snapshot()
        assert hw.gpu_backend == "none"
        assert hw.gpu_vram_total_gb == 0.0
        assert hw.gpu_vram_available_gb == 0.0
        assert hw.unified_memory is False
