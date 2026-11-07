"""Database integration: rent_stats loading and the seed fallback. Never touches a real DB."""

from typing import Any

import pytest
from sqlalchemy import create_engine

from haven.datasets import db
from haven.datasets.loaders import rents
from haven.store.db import DatabaseNotConfiguredError


@pytest.fixture(autouse=True)
def no_real_database(monkeypatch: pytest.MonkeyPatch) -> None:
    def unconfigured() -> Any:
        raise DatabaseNotConfiguredError("no database in tests")

    monkeypatch.setattr(db, "get_engine", unconfigured)


def test_rent_series_falls_back_to_seed_without_a_database() -> None:
    series = db.rent_series("2_bed")
    assert series.source == "seed"
    assert [r["year"] for r in series.records] == list(range(2010, 2026))
    assert series.records[-1]["mean_gbp_pcm"] == 1356.43
    assert set(series.records[0]) == set(db.RENT_COLUMNS)


def test_rent_series_falls_back_when_the_database_is_unreachable() -> None:
    engine = create_engine("sqlite://")  # has no rent_stats table: query fails
    series = db.rent_series("1_bed", engine)
    assert series.source == "seed"


def test_rent_series_reads_the_database_when_loaded() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "create table rent_stats (brma text, beds text, period_end date, year int, "
            "lower_quartile_gbp_pcm real, median_gbp_pcm real, mean_gbp_pcm real, "
            "upper_quartile_gbp_pcm real, n_records int, is_sample bool)"
        )
        conn.exec_driver_sql(
            "insert into rent_stats values "
            "('Lothian', '1_bed', '2025-09-30', 2025, 900, 1000, 1057.47, 1165, 1754, 0)"
        )
    series = db.rent_series("1_bed", engine)
    assert series.source == "database"
    assert series.records[0]["mean_gbp_pcm"] == 1057.47


def test_rent_series_rejects_unknown_category() -> None:
    with pytest.raises(ValueError):
        db.rent_series("studio")


def test_load_rent_stats_runs_the_generated_script() -> None:
    executed: list[str] = []

    class Conn:
        def exec_driver_sql(self, sql: str) -> None:
            executed.append(sql)

        def execute(self, *_: Any) -> Any:
            class Result:
                def scalar_one(self) -> int:
                    return 80

            return Result()

        def __enter__(self) -> "Conn":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    class Engine:
        def begin(self) -> Conn:
            return Conn()

    assert db.load_rent_stats(Engine()) == 80  # type: ignore[arg-type]
    assert executed == [rents.SQL_PATH.read_text(encoding="utf-8")]
