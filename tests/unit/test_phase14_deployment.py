"""Unit tests for Phase 14: Deployment Package & Configuration."""

from pathlib import Path

import pytest

from neo_wilder.domain.enums import ExecutionMode
from neo_wilder.main import NeoWilderApplication


def test_systemd_service_unit():
    """Verify systemd service unit enforces 400M memory cap, 150% CPU, and non-root user."""
    service_path = Path("deploy/neo-wilder.service")
    assert service_path.exists(), "deploy/neo-wilder.service must exist"

    content = service_path.read_text(encoding="utf-8")
    assert "MemoryMax=400M" in content
    assert "MemoryHigh=350M" in content
    assert "CPUQuota=150%" in content
    assert "Restart=always" in content
    assert "User=neowilder" in content
    assert "Group=neowilder" in content
    assert "NoNewPrivileges=true" in content
    assert "SyslogIdentifier=neo-wilder" in content


def test_env_example_template():
    """Verify env template contains required parameters and zero secrets."""
    env_path = Path("deploy/neo-wilder.env.example")
    assert env_path.exists(), "deploy/neo-wilder.env.example must exist"

    content = env_path.read_text(encoding="utf-8")
    assert "NEO_WILDER_MODE=SIGNAL" in content
    assert "TELEGRAM_BOT_TOKEN=" in content
    assert "TELEGRAM_CHAT_ID=" in content
    assert "DB_PATH=" in content
    assert "STRICT SECURITY WARNING" in content
    assert "SIGNAL_ONLY" in content


@pytest.mark.asyncio
async def test_application_initialization(tmp_path: Path, monkeypatch):
    """Verify NeoWilderApplication starts and shuts down cleanly."""
    from unittest.mock import AsyncMock

    monkeypatch.setenv("DB_PATH", str(tmp_path / "app_test.db"))

    app = NeoWilderApplication(mode=ExecutionMode.SIGNAL)
    assert app.mode == ExecutionMode.SIGNAL
    assert app.store is not None
    assert app.s1_strategy is not None

    # Mock network calls for instant test execution
    app.binance_rest.get_server_time_ms = AsyncMock(return_value=1730900000000)
    app.universe_manager.initialize_universe = AsyncMock(return_value=["BTCUSDT", "ETHUSDT"])

    # Test startup and immediate shutdown
    await app.start()
    assert app.store._running is True

    await app.stop()
    assert app.store._running is False
