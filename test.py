"""
API Test Suite for Flask Leaderboard Application
Tests: /add, /leaderboard, /remove, /info, /performance endpoints
"""

import requests
import json
import sys
from dataclasses import dataclass, field
from typing import Any

BASE_URL = "http://127.0.0.1:5000"

# ── ANSI colours ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ── Result tracking ──────────────────────────────────────────────────────────
@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""
    details: Any = None

results: list[TestResult] = []

def run(name: str, fn):
    """Run a single test function and record the result."""
    try:
        fn()
        results.append(TestResult(name, True))
        print(f"  {GREEN}✓{RESET} {name}")
    except AssertionError as e:
        results.append(TestResult(name, False, str(e)))
        print(f"  {RED}✗{RESET} {name}")
        print(f"    {YELLOW}→ {e}{RESET}")
    except Exception as e:
        results.append(TestResult(name, False, f"Unexpected error: {e}"))
        print(f"  {RED}✗{RESET} {name}")
        print(f"    {YELLOW}→ Unexpected error: {e}{RESET}")

def section(title: str):
    print(f"\n{CYAN}{BOLD}▸ {title}{RESET}")

def assert_status(resp, expected):
    assert resp.status_code == expected, (
        f"Expected HTTP {expected}, got {resp.status_code}. Body: {resp.text[:200]}"
    )

def assert_json_key(data: dict, key: str):
    assert key in data, f"Key '{key}' missing from response: {list(data.keys())}"


# ── Helpers ──────────────────────────────────────────────────────────────────
def add_entry(name: str, score: float) -> requests.Response:
    return requests.post(
        f"{BASE_URL}/add",
        json={"name": name, "score": score},
        headers={"Content-Type": "application/json"},
    )

def remove_entry(name: str) -> requests.Response:
    return requests.delete(
        f"{BASE_URL}/remove",
        json={"name": name},
        headers={"Content-Type": "application/json"},
    )



requests.delete(f"{BASE_URL}/reset")

# ────────────────────────────────────────────────────────────────────────────
# POST /add
# ────────────────────────────────────────────────────────────────────────────
section("POST /add")

def test_add_valid():
    resp = add_entry("Alice", 42.0)
    assert_status(resp, 201)
    data = resp.json()
    assert_json_key(data, "success")


def test_add_missing_score():
    resp = requests.post(f"{BASE_URL}/add", json={"name": "Bob"})
    assert_status(resp, 400)
    assert_json_key(resp.json(), "error")

def test_add_missing_name():
    resp = requests.post(f"{BASE_URL}/add", json={"score": 10})
    assert_status(resp, 400)
    assert_json_key(resp.json(), "error")

def test_add_empty_body():
    resp = requests.post(f"{BASE_URL}/add", json={})
    assert_status(resp, 400)

def test_add_non_json_content_type():
    resp = requests.post(
        f"{BASE_URL}/add",
        data="name=Alice&score=10",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert_status(resp, 400)

def test_add_no_body():
    resp = requests.post(f"{BASE_URL}/add")
    assert_status(resp, 400)

def test_add_negative_score():
    """Negative scores are valid numbers; the API should accept them."""
    resp = add_entry("NegativeCarl", -5.0)
    assert_status(resp, 201)

def test_add_zero_score():
    resp = add_entry("ZeroZara", 0)
    assert_status(resp, 201)

def test_add_string_score():
    """A non-numeric score string — server may accept or reject; just ensure no 500."""
    resp = requests.post(f"{BASE_URL}/add", json={"name": "StringScore", "score": "abc"})
    assert resp.status_code in (201, 400), f"Expected 201 or 400, got {resp.status_code}"

for fn in [
    test_add_valid, test_add_missing_score,
    test_add_missing_name, test_add_empty_body, test_add_non_json_content_type,
    test_add_no_body, test_add_negative_score, test_add_zero_score,
    test_add_string_score,
]:
    run(fn.__doc__ or fn.__name__.replace("_", " "), fn)


# ────────────────────────────────────────────────────────────────────────────
# Seed data for remaining tests
# ────────────────────────────────────────────────────────────────────────────
SEED = [("Alice", 95), ("Bob", 80), ("Charlie", 70), ("Diana", 60),
        ("Eve", 55), ("Frank", 50), ("Grace", 45), ("Hank", 40),
        ("Ivy", 30), ("Jack", 20), ("Karen", 10)]
for name, score in SEED:
    add_entry(name, score)


# ────────────────────────────────────────────────────────────────────────────
# GET /leaderboard
# ────────────────────────────────────────────────────────────────────────────
section("GET /leaderboard")

def test_leaderboard_returns_200():
    resp = requests.get(f"{BASE_URL}/leaderboard")
    assert_status(resp, 200)

def test_leaderboard_is_list():
    resp = requests.get(f"{BASE_URL}/leaderboard")
    assert isinstance(resp.json(), list), "Response should be a JSON array"

def test_leaderboard_max_10():
    resp = requests.get(f"{BASE_URL}/leaderboard")
    assert len(resp.json()) <= 10, "Leaderboard should return at most 10 entries"

def test_leaderboard_entry_fields():
    resp = requests.get(f"{BASE_URL}/leaderboard")
    entries = resp.json()
    assert entries, "Leaderboard is empty"
    for entry in entries:
        for key in ("name", "score", "time"):
            assert_json_key(entry, key)

def test_leaderboard_descending_order():
    resp = requests.get(f"{BASE_URL}/leaderboard")
    scores = [e["score"] for e in resp.json()]
    assert scores == sorted(scores, reverse=True), (
        f"Scores not in descending order: {scores}"
    )

for fn in [
    test_leaderboard_returns_200, test_leaderboard_is_list,
    test_leaderboard_max_10, test_leaderboard_entry_fields,
    test_leaderboard_descending_order,
]:
    run(fn.__doc__ or fn.__name__.replace("_", " "), fn)


# ────────────────────────────────────────────────────────────────────────────
# DELETE /remove
# ────────────────────────────────────────────────────────────────────────────
section("DELETE /remove")

def test_remove_existing_entry():
    add_entry("ToDelete", 1.0)
    resp = remove_entry("ToDelete")
    assert_status(resp, 200)
    assert_json_key(resp.json(), "success")

def test_remove_nonexistent_entry():
    """Removing a name not in the DB should still return 200 (no error)."""
    resp = remove_entry("DoesNotExist_XYZ")
    assert_status(resp, 200)

def test_remove_missing_name_field():
    resp = requests.delete(f"{BASE_URL}/remove", json={"wrong": "field"})
    assert_status(resp, 400)

def test_remove_no_body():
    resp = requests.delete(f"{BASE_URL}/remove")
    assert_status(resp, 400)

def test_remove_actually_deletes():
    add_entry("Ephemeral", 5.0)
    remove_entry("Ephemeral")
    board = requests.get(f"{BASE_URL}/leaderboard").json()
    names = [e["name"] for e in board]
    assert "Ephemeral" not in names, "Entry was not actually removed from leaderboard"

for fn in [
    test_remove_existing_entry, test_remove_nonexistent_entry,
    test_remove_missing_name_field, test_remove_no_body,
    test_remove_actually_deletes,
]:
    run(fn.__doc__ or fn.__name__.replace("_", " "), fn)


# ────────────────────────────────────────────────────────────────────────────
# GET /info
# ────────────────────────────────────────────────────────────────────────────
section("GET /info")

EXPECTED_INFO_KEYS = {"mean", "median", "quartiles", "iqr", "skew", "standard deviation"}

def test_info_returns_200():
    resp = requests.get(f"{BASE_URL}/info")
    assert_status(resp, 200)

def test_info_has_required_keys():
    data = requests.get(f"{BASE_URL}/info").json()
    missing = EXPECTED_INFO_KEYS - data.keys()
    assert not missing, f"Missing keys in /info response: {missing}"

def test_info_mean_is_number():
    data = requests.get(f"{BASE_URL}/info").json()
    assert isinstance(data["mean"], (int, float)), "mean should be numeric"

def test_info_quartiles_is_list_of_4():
    data = requests.get(f"{BASE_URL}/info").json()
    q = data["quartiles"]
    assert hasattr(q, "__len__") and len(q) == 4, (
        f"quartiles should have 4 elements, got: {q}"
    )

def test_info_iqr_non_negative():
    data = requests.get(f"{BASE_URL}/info").json()
    assert data["iqr"] >= 0, f"IQR should be ≥ 0, got {data['iqr']}"

def test_info_std_dev_non_negative():
    data = requests.get(f"{BASE_URL}/info").json()
    assert data["standard deviation"] >= 0, (
        f"Standard deviation should be ≥ 0, got {data['standard deviation']}"
    )

def test_info_skew_is_number():
    data = requests.get(f"{BASE_URL}/info").json()
    assert isinstance(data["skew"], (int, float)), "skew should be numeric"

for fn in [
    test_info_returns_200, test_info_has_required_keys,
    test_info_mean_is_number, test_info_quartiles_is_list_of_4,
    test_info_iqr_non_negative, test_info_std_dev_non_negative,
    test_info_skew_is_number,
]:
    run(fn.__doc__ or fn.__name__.replace("_", " "), fn)


# ────────────────────────────────────────────────────────────────────────────
# GET /performance
# ────────────────────────────────────────────────────────────────────────────
section("GET /performance")

def test_performance_returns_200():
    resp = requests.get(f"{BASE_URL}/performance")
    assert_status(resp, 200)

def test_performance_is_dict():
    data = requests.get(f"{BASE_URL}/performance").json()
    assert isinstance(data, dict), "Response should be a JSON object"

def test_performance_values_are_positive():
    data = requests.get(f"{BASE_URL}/performance").json()
    for endpoint, avg in data.items():
        assert avg >= 0, f"Negative average time for endpoint '{endpoint}': {avg}"

def test_performance_tracks_called_endpoints():
    data = requests.get(f"{BASE_URL}/performance").json()
    # We've called /add, /leaderboard, /remove, /info, /performance — at least
    # some of these should appear in the averages dict.
    assert len(data) > 0, "Performance dict is empty after multiple requests"

for fn in [
    test_performance_returns_200, test_performance_is_dict,
    test_performance_values_are_positive, test_performance_tracks_called_endpoints,
]:
    run(fn.__doc__ or fn.__name__.replace("_", " "), fn)

# ────────────────────────────────────────────────────────────────────────────
# GET /predict
# ────────────────────────────────────────────────────────────────────────────
section("GET /predictions")

EXPECTED_PREDICT_KEYS = {"team", "avg_lap_time", "trend", "predicted_score", "laps_recorded"}

def test_predict_returns_200():
    resp = requests.get(f"{BASE_URL}/predictions")
    assert_status(resp, 200)

def test_predict_is_list():
    resp = requests.get(f"{BASE_URL}/predictions")
    assert isinstance(resp.json(), list), "Response should be a JSON array"

def test_predict_has_required_keys():
    data = requests.get(f"{BASE_URL}/predictions").json()
    assert data, "Predict returned empty list"
    for entry in data:
        missing = EXPECTED_PREDICT_KEYS - entry.keys()
        assert not missing, f"Missing keys in /predictions entry: {missing}"

def test_predict_avg_lap_time_is_number():
    data = requests.get(f"{BASE_URL}/predictions").json()
    for entry in data:
        assert isinstance(entry["avg_lap_time"], (int, float)), \
            f"avg_lap_time should be numeric for team {entry['team']}"

def test_predict_laps_recorded_is_positive():
    data = requests.get(f"{BASE_URL}/predictions").json()
    for entry in data:
        assert entry["laps_recorded"] > 0, \
            f"laps_recorded should be > 0 for team {entry['team']}"

def test_predict_sorted_ascending():
    """Predictions should be sorted by predicted_score ascending (lower = faster = better)."""
    data = requests.get(f"{BASE_URL}/predictions").json()
    scores = [e["predicted_score"] for e in data]
    assert scores == sorted(scores), f"Predictions not sorted ascending: {scores}"

def test_predict_exactly_one_winner():
    """Exactly one entry should have predicted_winner set to True."""
    data = requests.get(f"{BASE_URL}/predictions").json()
    winners = [e for e in data if e.get("predicted_winner") == True]
    assert len(winners) == 1, f"Expected exactly 1 predicted_winner, got {len(winners)}"

def test_predict_winner_has_lowest_score():
    """The predicted_winner should be the entry with the lowest predicted_score."""
    data = requests.get(f"{BASE_URL}/predictions").json()
    winner = next((e for e in data if e.get("predicted_winner")), None)
    assert winner is not None, "No predicted_winner found"
    lowest = min(data, key=lambda e: e["predicted_score"])
    assert winner["team"] == lowest["team"], \
        f"Winner {winner['team']} doesn't have the lowest predicted_score"

def test_predict_trend_is_number():
    data = requests.get(f"{BASE_URL}/predictions").json()
    for entry in data:
        assert isinstance(entry["trend"], (int, float)), \
            f"trend should be numeric for team {entry['team']}"

def test_predict_empty_db_returns_400():
    """If no lap data exists, /predict should return 400."""
    requests.delete(f"{BASE_URL}/reset")
    resp = requests.get(f"{BASE_URL}/predictions")
    assert_status(resp, 400)
    # Re-seed so later tests aren't affected
    for name, score in SEED:
        add_entry(name, score)

for fn in [
    test_predict_returns_200, test_predict_is_list,
    test_predict_has_required_keys, test_predict_avg_lap_time_is_number,
    test_predict_laps_recorded_is_positive, test_predict_sorted_ascending,
    test_predict_exactly_one_winner, test_predict_winner_has_lowest_score,
    test_predict_trend_is_number, test_predict_empty_db_returns_400,
]:
    run(fn.__doc__ or fn.__name__.replace("_", " "), fn)




# ────────────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────────────
passed = sum(1 for r in results if r.passed)
total  = len(results)
failed = total - passed

print(f"\n{BOLD}{'─'*50}{RESET}")
print(f"{BOLD}Results: {GREEN}{passed} passed{RESET}{BOLD}, "
      f"{RED}{failed} failed{RESET}{BOLD} / {total} total{RESET}")

if failed:
    print(f"\n{RED}{BOLD}Failed tests:{RESET}")
    for r in results:
        if not r.passed:
            print(f"  • {r.name}: {r.message}")

print()
sys.exit(0 if failed == 0 else 1)