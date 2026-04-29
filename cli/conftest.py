"""Pytest configuration for the Beckett test suite."""

from __future__ import annotations

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: requires BECKETT_MODEL and real API credentials (skipped by default)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip @pytest.mark.live tests unless BECKETT_MODEL is set."""
    if os.environ.get("BECKETT_MODEL"):
        return
    skip_live = pytest.mark.skip(reason="BECKETT_MODEL not set (pass -m live to opt in)")
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(skip_live)
