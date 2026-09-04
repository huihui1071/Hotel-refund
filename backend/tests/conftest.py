import os

import pytest


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    target = tmp_path / "qunar-test.db"
    monkeypatch.setenv("QUNAR_MOCK_DB", str(target))
    from app.db import init_database

    init_database(reset=True)
    return target

