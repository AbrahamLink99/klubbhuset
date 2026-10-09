import pytest

from klubbhuset_motor.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "arkiv" / "klubbhuset.db")
    yield s
    s.conn.close()
