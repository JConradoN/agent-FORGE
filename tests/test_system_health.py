import pytest
from unittest.mock import patch, MagicMock

from agentforge.tools.system_health import collect_system_health


class TestSystemHealthTool:
    def test_collect_returns_dict(self):
        result = collect_system_health()
        assert isinstance(result, dict)

    def test_collect_has_expected_keys(self):
        result = collect_system_health()
        expected_keys = [
            "timestamp",
            "hostname",
            "cpu",
            "memory",
            "disk",
            "gpu",
            "top_processes_cpu",
            "top_processes_memory",
            "alerts",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_cpu_has_usage_percent(self):
        result = collect_system_health()
        assert "usage_percent" in result["cpu"]
        assert isinstance(result["cpu"]["usage_percent"], (int, float))

    def test_memory_has_usage_and_available(self):
        result = collect_system_health()
        assert "usage_percent" in result["memory"]
        assert "available_mb" in result["memory"]

    def test_disk_has_usage_and_free(self):
        result = collect_system_health()
        assert "root_usage_percent" in result["disk"]
        assert "free_gb" in result["disk"]

    def test_top_processes_are_lists(self):
        result = collect_system_health()
        assert isinstance(result["top_processes_cpu"], list)
        assert isinstance(result["top_processes_memory"], list)
        assert len(result["top_processes_cpu"]) <= 5
        assert len(result["top_processes_memory"]) <= 5

    def test_alerts_is_list(self):
        result = collect_system_health()
        assert isinstance(result["alerts"], list)

    @patch("subprocess.run")
    def test_gpu_null_when_nvidia_smi_missing(self, mock_run):
        mock_run.side_effect = FileNotFoundError("nvidia-smi not found")
        result = collect_system_health()
        assert result["gpu"] is None

    @patch("subprocess.run")
    def test_gpu_data_when_nvidia_smi_available(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="GeForce RTX 3060, 45, 55, 4096, 12288\n",
        )
        result = collect_system_health()
        assert result["gpu"] is not None
        assert result["gpu"]["name"] == "GeForce RTX 3060"
        assert result["gpu"]["utilization"] == 45
        assert result["gpu"]["temperature"] == 55
        assert result["gpu"]["vram_used_mb"] == 4096
        assert result["gpu"]["vram_total_mb"] == 12288

    def test_alerts_cpu_high(self):
        with patch("psutil.cpu_percent", return_value=90.0):
            result = collect_system_health()
            assert "cpu_high" in result["alerts"]

    def test_alerts_memory_high(self):
        with patch.object(
            MagicMock(),
            "percent",
            create=True,
            return_value=95.0,
        ):
            import psutil
            with patch.object(psutil, "virtual_memory") as mock_mem:
                mock_mem.return_value = MagicMock(percent=95.0, available=1024*1024*100)
                result = collect_system_health()
                assert "memory_high" in result["alerts"] or "memory_high" in result.get("alerts", [])