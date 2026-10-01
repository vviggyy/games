"""Vercel serverless function: post or delete a suggestion in suggestions.json via GitHub API."""

import base64
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

REPO = "vviggyy/games"
JSON_PATH = "suggestions.json"
BRANCH = "main"

MAX_TEXT = 500
MAX_NAME = 24


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


def clean(text, limit):
    text = re.sub(r"[ \t]+", " ", str(text)).strip()
    text = "".join(ch for ch in text if ch.isprintable() or ch == "\n")
    return text[:limit]


def commit(suggestions, sha, message, token):
    content = json.dumps(suggestions, indent=2, sort_keys=True) + "\n"
    github_request(
        JSON_PATH,
        method="PUT",
        body={
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "sha": sha,
            "branch": BRANCH,
        },
        token=token,
    )


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

        action = payload.get("action", "add")

        try:
            file_info = github_request(JSON_PATH, token=token)
        except Exception as e:
            self._json(500, {"error": f"Failed to fetch suggestions: {e}"})
            return

        sha = file_info["sha"]
        try:
            suggestions = json.loads(base64.b64decode(file_info["content"]).decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            suggestions = []
        if not isinstance(suggestions, list):
            suggestions = []

        if action == "delete":
            admin_pw = os.environ.get("ADMIN_PASSWORD")
            if not admin_pw:
                self._json(500, {"error": "ADMIN_PASSWORD not configured"})
                return
            password = payload.get("password", "")
            if not password or not hmac.compare_digest(str(password), admin_pw):
                self._json(403, {"error": "Wrong password"})
                return

            target = payload.get("id")
            kept = [s for s in suggestions if s.get("id") != target]
            if len(kept) == len(suggestions):
                self._json(404, {"error": "No matching suggestion"})
                return
            try:
                commit(kept, sha, f"Delete suggestion {target}", token)
            except Exception as e:
                self._json(500, {"error": f"Failed to commit: {e}"})
                return
            self._json(200, {"ok": True, "removed": 1})
            return

        name = clean(payload.get("name", ""), MAX_NAME) or "Anonymous"
        text = clean(payload.get("text", ""), MAX_TEXT)
        if not text:
            self._json(400, {"error": "Suggestion cannot be empty"})
            return

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sid = hashlib.sha256(f"{name}{text}{ts}".encode()).hexdigest()[:12]
        suggestions.append({"id": sid, "name": name, "text": text, "ts": ts})

        try:
            commit(suggestions, sha, f"Suggestion from {name}", token)
        except Exception as e:
            self._json(500, {"error": f"Failed to commit: {e}"})
            return

        self._json(200, {"ok": True, "id": sid, "ts": ts, "name": name})

    def _json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
