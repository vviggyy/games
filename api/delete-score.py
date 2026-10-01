"""Vercel serverless function: delete a score row from scores.csv via GitHub API."""

import base64
import csv
import hmac
import io
import json
import os
from http.server import BaseHTTPRequestHandler

REPO = "vviggyy/games"
CSV_PATH = "scores.csv"
BRANCH = "main"
HEADER = ["date", "game", "player", "score", "percentile"]


def github_request(path, method="GET", body=None, token=None):
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


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        admin_pw = os.environ.get("ADMIN_PASSWORD")
        if not admin_pw:
            self._json(500, {"error": "ADMIN_PASSWORD not configured"})
            return

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

        password = payload.get("password", "")
        if not password or not hmac.compare_digest(str(password), admin_pw):
            self._json(403, {"error": "Wrong password"})
            return

        date = payload.get("date")
        game = payload.get("game")
        player = payload.get("player")
        if not date or not game or not player:
            self._json(400, {"error": "Missing date, game, or player"})
            return

        try:
            file_info = github_request(CSV_PATH, token=token)
        except Exception as e:
            self._json(500, {"error": f"Failed to fetch CSV: {e}"})
            return

        sha = file_info["sha"]
        csv_content = base64.b64decode(file_info["content"]).decode("utf-8")

        rows = list(csv.DictReader(io.StringIO(csv_content)))
        kept = [
            r for r in rows
            if not (r["date"] == date and r["game"] == game and r["player"] == player)
        ]
        removed = len(rows) - len(kept)
        if removed == 0:
            self._json(404, {"error": "No matching score found"})
            return

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=HEADER, lineterminator="\n", restval="")
        writer.writeheader()
        writer.writerows(kept)

        commit_msg = f"Delete {game} score for {player} on {date}"
        try:
            github_request(
                CSV_PATH,
                method="PUT",
                body={
                    "message": commit_msg,
                    "content": base64.b64encode(buf.getvalue().encode("utf-8")).decode("ascii"),
                    "sha": sha,
                    "branch": BRANCH,
                },
                token=token,
            )
        except Exception as e:
            self._json(500, {"error": f"Failed to commit: {e}"})
            return

        self._json(200, {"ok": True, "removed": removed})

    def _json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
