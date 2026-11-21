"""A restarted harvester continues its current round instead of starting over.

Covers scraper/jobthai_harvester.py (listings already scanned in the round are not requested
again; after discover finished a restart goes straight to fetch) and scraper/jobbkk_harvester.py
(finished provinces are skipped, the province it was in continues after last_page).
Fully offline: polite_get / time.sleep are replaced, no request leaves the machine.
"""
from __future__ import annotations

import importlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LISTING_HTML = (Path(__file__).parent / "fixtures" / "jobthai_listing_sample.html").read_text(encoding="utf-8")

ROUND_START = "2026-11-21T09:00:00+00:00"
IN_ROUND = "2026-11-21T10:00:00+00:00"
BEFORE_ROUND = "2026-11-20T10:00:00+00:00"


def _modules():
    sys.path.insert(0, str(REPO_ROOT / "scraper"))
    return importlib.import_module("jobthai_harvester"), importlib.import_module("jobbkk_harvester")


@pytest.fixture()
def jt(tmp_path, monkeypatch):
    mod, _ = _modules()
    monkeypatch.setattr(mod, "DB", str(tmp_path / "jobthai.sqlite"))
    monkeypatch.setattr(mod, "log", lambda msg: None)
    return mod


@pytest.fixture()
def bk(tmp_path, monkeypatch):
    _, mod = _modules()
    monkeypatch.setattr(mod, "DB", str(tmp_path / "jobbkk.sqlite"))
    monkeypatch.setattr(mod, "PROVINCES", ["A", "B", "C"])
    monkeypatch.setattr(mod, "log", lambda msg: None)
    return mod


def _requests(jt, monkeypatch):
    asked = []
    monkeypatch.setattr(jt, "polite_get", lambda url: asked.append(url) or LISTING_HTML)
    return asked


def test_jobthai_restart_skips_listings_scanned_earlier_in_the_round(jt, monkeypatch):
    con = jt.db()
    con.executemany(
        "INSERT INTO listing(url, last_scanned, total) VALUES (?,?,?)",
        [("a", IN_ROUND, 3), ("b", IN_ROUND, 7), ("c", BEFORE_ROUND, 5), ("d", None, None), ("e", None, None)],
    )
    jt.meta_set(con, round_started=ROUND_START)  # discover of this round was cut off
    asked = _requests(jt, monkeypatch)

    jt.discover(con)

    # missing N_h first, then the oldest scan; a and b (done earlier this round) are not asked again
    assert sorted(asked[:2]) == ["d", "e"] and asked[2:] == ["c"]
    assert dict(con.execute("SELECT url, last_scanned FROM listing WHERE url IN ('a','b')")) == {
        "a": IN_ROUND, "b": IN_ROUND}
    assert jt.meta_get(con, "round_started") == ROUND_START
    assert jt.meta_get(con, "discover_done")
    assert jt.next_step(con, 12) == ("fetch", 0.0)


def test_jobthai_new_round_scans_every_listing(jt, monkeypatch):
    con = jt.db()
    con.executemany("INSERT INTO listing(url, last_scanned, total) VALUES (?,?,?)",
                    [("a", IN_ROUND, 3), ("b", None, None)])
    jt.meta_set(con, round_started=ROUND_START, discover_done=IN_ROUND, round_done=IN_ROUND)
    asked = _requests(jt, monkeypatch)

    jt.discover(con)

    assert sorted(asked) == ["a", "b"]
    assert jt.meta_get(con, "round_started") > IN_ROUND
    assert jt.meta_get(con, "round_done") is None


def test_next_step_follows_the_round(jt):
    con = jt.db()
    assert jt.next_step(con, 12) == ("discover", 0.0)  # nothing yet
    started, resumed = jt.begin_discover(con)
    assert not resumed
    assert jt.begin_discover(con) == (started, True)  # restart during discover -> same round
    assert jt.next_step(con, 12) == ("discover", 0.0)

    jt.meta_set(con, discover_done=now_iso())
    assert jt.next_step(con, 12) == ("fetch", 0.0)  # restart during fetch

    done = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
    jt.meta_set(con, round_done=done.isoformat())
    step, left = jt.next_step(con, 12, at=done + timedelta(hours=1))
    assert step == "wait" and left == pytest.approx(11 * 3600)  # restart during the pause
    assert jt.next_step(con, 12, at=done + timedelta(hours=13)) == ("discover", 0.0)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class _Stop(Exception):
    pass


def test_run_after_restart_in_fetch_phase_does_not_discover_again(jt, monkeypatch):
    con = jt.db()
    jt.meta_set(con, round_started=ROUND_START, discover_done=IN_ROUND)
    calls = []

    def sleep(seconds):
        raise _Stop

    monkeypatch.setattr(jt.time, "sleep", sleep)
    with pytest.raises(_Stop):
        jt.run_rounds(con, lambda c: calls.append("discover"), lambda c: calls.append("fetch"),
                      lambda c: calls.append("export"), lambda c: calls.append("stats"), 12, lambda m: None)

    assert calls == ["fetch", "export", "stats"]
    assert jt.meta_get(con, "round_done")
    assert jt.next_step(con, 12)[0] == "wait"


def test_jobbkk_resume_point():
    _, bk = _modules()
    assert bk.resume_point(None, 0) == (1, None, 1)  # province not started in this round
    assert bk.resume_point(20141, 40) == (41, 20141, 806)  # 25 per page
    assert bk.resume_point(100, 4, max_pages=2) == (5, 100, 2)  # already past BK_MAX_PAGES -> nothing left
    assert bk.resume_point(0, 3) == (1, None, 1)


def test_jobbkk_restart_keeps_page_progress_new_round_resets_it(bk):
    con = bk.db()
    con.execute("UPDATE province SET last_page=40, total=20141 WHERE name='A'")  # in progress
    con.execute("UPDATE province SET last_page=9, total=200, last_scanned=? WHERE name='B'", (IN_ROUND,))  # done
    con.execute("UPDATE province SET last_page=0, last_scanned=? WHERE name='C'", (BEFORE_ROUND,))
    bk.meta_set(con, round_started=ROUND_START)

    rows = bk.provinces_to_scan(con)  # restart in the middle of the round

    assert [r[0] for r in rows] == ["A", "C"]
    assert bk.resume_point(*rows[0][1:]) == (41, 20141, 806)
    assert bk.resume_point(*rows[1][1:]) == (1, None, 1)

    bk.meta_set(con, discover_done=IN_ROUND)
    rows = bk.provinces_to_scan(con)  # next round

    assert sorted(r[0] for r in rows) == ["A", "B", "C"]
    assert {r[2] for r in rows} == {0}  # every province starts again at page 1
