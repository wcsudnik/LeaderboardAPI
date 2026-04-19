"""
Little 500 Race Simulator
--------------------------
Simulates 200 laps of the Little 500 with per-team fatigue degradation.
Posts each lap to the leaderboard API in real time and prints a live
terminal display as the race progresses.

Usage:
    python simulate_race.py
    python simulate_race.py --teams 8 --delay 0.3 --laps 200
    (Start leaderboard-server first; API defaults to http://127.0.0.1:3001)
"""

import argparse
import os
import random
import time
import requests
from dataclasses import dataclass, field

# Match leaderboard-server default (PORT=3001). Override with env or --base-url.
DEFAULT_BASE_URL = os.environ.get("LEADERBOARD_BASE_URL", "http://127.0.0.1:3001").rstrip("/")

# ── ANSI colours ─────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
WHITE  = "\033[97m"

# ── Little 500 Teams ──────────────────────────────────────────────────────────
DEFAULT_TEAMS = [
    "Cutters",
    "Phi Kappa Psi",
    "Sigma Nu",
    "Delta Tau Delta",
    "Beta Theta Pi",
    "Dodds House",
    "Willkie North",
    "Eigenmann",
]


@dataclass
class Team:
    name: str
    base_lap_time: float = field(init=False)  # seconds per lap
    fatigue_rate:  float = field(init=False)  # seconds added per lap
    fatigue:       float = field(default=0.0)
    laps:          list  = field(default_factory=list)
    total_time:    float = field(default=0.0)

    def __post_init__(self):
        self.base_lap_time = random.uniform(58.0, 68.0)
        self.fatigue_rate  = random.uniform(0.010, 0.035)

    def ride_lap(self) -> float:
        noise    = random.gauss(0, 0.8)
        incident = random.random() < 0.004          # ~0.4% crash/mechanical chance
        extra    = random.uniform(5, 20) if incident else 0.0
        lap_time = self.base_lap_time + self.fatigue + noise + extra
        lap_time = max(lap_time, 50.0)              # physical lower bound
        self.fatigue    += self.fatigue_rate
        self.total_time += lap_time
        self.laps.append(round(lap_time, 3))
        return round(lap_time, 3)


def post_lap(session: requests.Session, base_url: str, name: str, lap_time: float):
    try:
        session.post(
            f"{base_url}/add",
            json={"user": name, "score": lap_time},
            timeout=3,
        )
    except requests.RequestException as e:
        print(f"  {YELLOW}⚠  API error posting {name}: {e}{RESET}")


def fetch_leaderboard(session: requests.Session, base_url: str) -> list:
    try:
        resp = session.get(f"{base_url}/leaderboard", timeout=3)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if isinstance(data, dict) and "top" in data:
            return data["top"]
        return data if isinstance(data, list) else []
    except requests.RequestException:
        return []


def render(teams: list, lap_times: dict, lap: int, total_laps: int,
           elapsed: float, board: list):
    print("\033[2J\033[H", end="")  # clear terminal

    # ── Header ────────────────────────────────────────────────────────────────
    bar_width = 40
    filled    = int(bar_width * lap / total_laps)
    bar       = "█" * filled + "░" * (bar_width - filled)
    print(f"{BOLD}{CYAN}{'═' * 58}{RESET}")
    print(f"{BOLD}{CYAN}   🚴  LITTLE 500 — LAP {lap}/{total_laps}   "
          f"({lap/total_laps*100:.1f}%)   {elapsed:.0f}s elapsed{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 58}{RESET}")
    print(f"  [{CYAN}{bar}{RESET}]\n")

    # ── This lap's times ──────────────────────────────────────────────────────
    print(f"  {BOLD}Lap {lap} times:{RESET}")
    sorted_lap = sorted(lap_times.items(), key=lambda x: x[1])
    for i, (name, t) in enumerate(sorted_lap):
        colour = GREEN if i == 0 else (RED if i == len(sorted_lap) - 1 else WHITE)
        medal  = "🥇" if i == 0 else "  "
        print(f"  {medal} {colour}{name:<22}{RESET} {t:.3f}s")

    # ── API leaderboard (best lap per team) ───────────────────────────────────
    print(f"\n  {BOLD}Leaderboard (best lap):{RESET}")
    if board:
        for i, entry in enumerate(board):
            colour = GREEN if i == 0 else WHITE
            rank   = f"{i+1}."
            label = entry.get("user") or entry.get("name", "")
            print(f"    {colour}{rank:<3} {label:<22}{RESET} {float(entry['score']):.3f}s")
    else:
        print(f"    {YELLOW}(no data yet){RESET}")

    # ── Race totals ───────────────────────────────────────────────────────────
    print(f"\n  {BOLD}Total race time:{RESET}")
    sorted_teams = sorted(teams, key=lambda t: t.total_time)
    for i, team in enumerate(sorted_teams):
        colour = GREEN if i == 0 else WHITE
        mins, secs = divmod(team.total_time, 60)
        print(f"    {colour}{i+1}. {team.name:<22}{RESET} {int(mins)}m {secs:.1f}s")

    print(f"\n{BOLD}{CYAN}{'═' * 58}{RESET}")


def simulate(team_names: list, total_laps: int, delay: float, base_url: str):
    teams = [Team(name=n) for n in team_names]

    print(f"{CYAN}{BOLD}Resetting leaderboard...{RESET}")
    with requests.Session() as session:
        try:
            r = session.delete(f"{base_url}/reset", timeout=5)
            r.raise_for_status()
        except requests.RequestException as e:
            print(
                f"{RED}Cannot reach leaderboard API at {base_url!r} ({e}).{RESET}\n"
                f"  Start the server from leaderboard-server (default port 3001), e.g.:\n"
                f"    npm run dev\n"
                f"  Or point the sim elsewhere: set LEADERBOARD_BASE_URL or pass --base-url.",
            )
            raise SystemExit(1) from e
        time.sleep(0.5)

        start = time.time()

        for lap in range(1, total_laps + 1):
            lap_times = {}

            # Each team rides the lap
            for team in teams:
                t = team.ride_lap()
                lap_times[team.name] = t
                post_lap(session, base_url, team.name, t)

            board   = fetch_leaderboard(session, base_url)
            elapsed = time.time() - start
            render(teams, lap_times, lap, total_laps, elapsed, board)

            time.sleep(delay)

        # ── Final results ─────────────────────────────────────────────────────
        print(f"\n{BOLD}{GREEN}  🏁  RACE COMPLETE!{RESET}\n")
        sorted_teams = sorted(teams, key=lambda t: t.total_time)
        print(f"  {BOLD}Final standings:{RESET}")
        for i, team in enumerate(sorted_teams):
            mins, secs = divmod(team.total_time, 60)
            colour = GREEN if i == 0 else WHITE
            medal  = ["🥇", "🥈", "🥉"][i] if i < 3 else "  "
            print(f"  {medal} {colour}{i+1}. {team.name:<22}{RESET} "
                  f"{int(mins)}m {secs:.1f}s  ({len(team.laps)} laps)")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Little 500 Race Simulator")
    parser.add_argument("--laps",  type=int,   default=200,  help="Number of laps (default: 200)")
    parser.add_argument("--delay", type=float, default=0.5,  help="Seconds between laps (default: 0.5)")
    parser.add_argument("--teams", type=str,   nargs="+",    help="Override team names")
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help=f"Leaderboard API root (default: env LEADERBOARD_BASE_URL or {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()

    team_names = args.teams if args.teams else DEFAULT_TEAMS
    base_url = (args.base_url or DEFAULT_BASE_URL).rstrip("/")
    simulate(team_names, args.laps, args.delay, base_url)