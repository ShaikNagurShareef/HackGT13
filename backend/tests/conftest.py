"""Shared fixtures: a tiny valid artifact bundle and the loaded Bundle object."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.repositories.artifacts import Bundle, load_bundle

from tests.bundle_factory import write_bundle, write_ride_bundle


@pytest.fixture(scope="session")
def bundle_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_bundle(tmp_path_factory.mktemp("bundle") / "pp-test-0001")


@pytest.fixture(scope="session")
def bundle(bundle_dir: Path) -> Bundle:
    return load_bundle(bundle_dir)


@pytest.fixture(scope="session")
def ride_bundle_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A walk bundle plus the mirrored ride model (ride_* files)."""
    root = write_bundle(tmp_path_factory.mktemp("ride-bundle") / "pp-test-0001")
    return write_ride_bundle(root)
