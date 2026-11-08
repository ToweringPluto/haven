"""Saved records: memory and SQL stores behave the same; ownership filters lists."""

import time

import pytest
from sqlmodel import create_engine

from haven.config import Settings
from haven.domain import RenterProfile
from haven.store import MemoryRecordStore, RecordStore, SqlRecordStore, db, make_record_store


def profile(pid: str, label: str = "x") -> RenterProfile:
    return RenterProfile(id=pid, label=label)


@pytest.fixture(params=["memory", "sql"])
def store(request: pytest.FixtureRequest) -> RecordStore:
    if request.param == "memory":
        return MemoryRecordStore()
    return SqlRecordStore(create_engine("sqlite://"))


def test_put_get_list_and_ownership(store: RecordStore) -> None:
    store.put("profile", profile("a"), owner_sub="alice")
    store.put("profile", profile("b"), owner_sub="bob")
    store.put("profile", profile("c"))
    assert store.get("profile", "a", RenterProfile) == profile("a")
    assert store.get("profile", "zzz", RenterProfile) is None
    assert store.get("report", "a", RenterProfile) is None  # kinds are separate
    assert [p.id for p in store.list("profile", RenterProfile, owner_sub="alice")] == ["a"]
    assert {p.id for p in store.list("profile", RenterProfile)} == {"a", "b", "c"}


def test_put_replaces(store: RecordStore) -> None:
    store.put("profile", profile("a", "old"), owner_sub="alice")
    store.put("profile", profile("a", "new"))
    stored = store.get("profile", "a", RenterProfile)
    assert stored is not None and stored.label == "new"
    assert [p.id for p in store.list("profile", RenterProfile, owner_sub="alice")] == ["a"]


def test_no_database_means_memory() -> None:
    assert isinstance(make_record_store(Settings()), MemoryRecordStore)


def test_unreachable_database_falls_back_to_memory() -> None:
    settings = Settings(database_url="postgresql://nobody:x@127.0.0.1:1/none?connect_timeout=1")
    assert isinstance(make_record_store(settings), MemoryRecordStore)


def test_blank_settings_count_as_unset() -> None:
    settings = Settings(database_url="", gemini_api_key="  ", vision_provider="")
    assert settings.database_url is None
    assert settings.gemini_api_key is None
    assert settings.vision_provider is None
    assert isinstance(make_record_store(settings), MemoryRecordStore)


def test_silently_dropped_database_falls_back_quickly(monkeypatch: pytest.MonkeyPatch) -> None:
    # 10.255.255.1 is non-routable: packets vanish like behind a firewall, so only the
    # default connect timeout (no timeout in the URL) stops startup from hanging.
    monkeypatch.setattr(db, "CONNECT_TIMEOUT_S", 1)
    settings = Settings(database_url="postgresql://nobody:x@10.255.255.1:5432/none")
    started = time.monotonic()
    assert isinstance(make_record_store(settings), MemoryRecordStore)
    assert time.monotonic() - started < 10


def test_list_skips_records_saved_in_an_older_format() -> None:
    from haven.domain import Upload

    store = MemoryRecordStore()
    store._rows[("upload", "old")] = ("auth0|u", {"id": "old", "kind": "floor_plan"})
    assert store.list("upload", Upload, owner_sub="auth0|u") == []
