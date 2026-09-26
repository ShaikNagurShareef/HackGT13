"""Shared fixtures: a tiny valid artifact bundle and the loaded Bundle object."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.repositories.artifacts import Bundle, load_bundle

from tests.bundle_factory import write_bundle


@pytest.fixture(scope="session")
def bundle_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_bundle(tmp_path_factory.mktemp("bundle") / "pp-test-0001")


@pytest.fixture(scope="session")
def bundle(bundle_dir: Path) -> Bundle:
    return load_bundle(bundle_dir)
