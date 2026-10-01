"""Vercel serverless function: add or update a score in scores.csv via GitHub API."""

import base64
import csv
import io
import json
import os
import re
from http.server import BaseHTTPRequestHandler

REPO = "vviggyy/games"
CSV_PATH = "scores.csv"
BRANCH = "main"
HEADER = ["date", "game", "player", "score"]

# Valid score range per game, mirroring the GAMES config in index.html.
GAME_RANGES = {
    "krillion": (0, 700),
    "wordle": (1, 7),
    "dialed_color": (0, 50),
    "dialed_sound": (0, 50),
}

MAX_NAME_LEN = 24


def github_request(path, method="GET", body=None, token=None):
    """Make a request to GitHub API using only stdlib."""
    import urllib.request

    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    if method == "GET":
        url += f"?ref={BRANCH}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "games-vercel",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def clean_name(name):
    """Collapse whitespace and strip control characters from a player name."""
    name = re.sub(r"\s+", " ", str(name)).strip()
    name = "".join(ch for ch in name if ch.isprintable())
    return name[:MAX_NAME_LEN]


def match_existing(name, existing_names):
    """Reuse an existing player's exact casing when the name matches case-insensitively."""
    lower = name.lower()
    for existing in existing_names:
        if existing.lower() == lower:
            return existing
    return name


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            self._json(500, {"error": "GITHUB_TOKEN not configured"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            self._json(400, {"error": "Invalid JSON"})
            return

        date = str(payload.get("date", ""))
        game = str(payload.get("game", ""))
        player = clean_name(payload.get("player", ""))

        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            self._json(400, {"error": "Date must be YYYY-MM-DD"})
            return
        if game not in GAME_RANGES:
            self._json(400, {"error": f"Unknown game '{game}'"})
            return
        if not player:
            self._json(400, {"error": "Missing player name"})
            return

        try:
            score = float(payload.get("score"))
        except (TypeError, ValueError):
            self._json(400, {"error": "Score must be a number"})
            return

        lo, hi = GAME_RANGES[game]
        if not (lo <= score <= hi):
            self._json(400, {"error": f"Score for {game} must be between {lo} and {hi}"})
            return

        # Store integers without a trailing .0 so the CSV stays readable.
        score_str = str(int(score)) if score == int(score) else f"{score:g}"

        try:
            file_info = github_request(CSV_PATH, token=token)
        except Exception as e:
            self._json(500, {"error": f"Failed to fetch CSV: {e}"})
            return

        sha = file_info["sha"]
        csv_content = base64.b64decode(file_info["content"]).decode("utf-8")

        rows = list(csv.DictReader(io.StringIO(csv_content)))
        existing_names = {r["player"] for r in rows}
        player = match_existing(player, existing_names)

        # One entry per player per game per day: replace in place if it exists.
        replaced = False
        for r in rows:
            if r["date"] == date and r["game"] == game and r["player"] == player:
                r["score"] = score_str
                replaced = True
                break
        if not replaced:
            rows.append({"date": date, "game": game, "player": player, "score": score_str})

        rows.sort(key=lambda r: (r["date"], r["game"], r["player"].lower()))

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        updated_csv = buf.getvalue()

        verb = "Update" if replaced else "Add"
        commit_msg = f"{verb} {game} score for {player} on {date} ({score_str})"
        try:
            github_request(
                CSV_PATH,
                method="PUT",
                body={
                    "message": commit_msg,
                    "content": base64.b64encode(updated_csv.encode("utf-8")).decode("ascii"),
                    "sha": sha,
                    "branch": BRANCH,
                },
                token=token,
            )
        except Exception as e:
            self._json(500, {"error": f"Failed to commit: {e}"})
            return

        self._json(200, {
            "ok": True,
            "updated": replaced,
            "date": date,
            "game": game,
            "player": player,
            "score": score_str,
        })

    def _json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
