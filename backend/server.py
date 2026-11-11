"""
Python Backend & Web Server for Build A 17-0 Team (Saison 2026/2027 - Ultimate Mode).
Serves both the REST API (/api/*) and static web assets (/),
includes a 1x daily background sync task, payload size limits,
HMAC anti-cheat validation, and supports Vercel Serverless via api/index.py.
"""
import hmac
import json
import mimetypes
import os
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BACKEND_DIR = Path(__file__).parent
STATIC_DIR = BACKEND_DIR / "static"
STATIC_HTML = STATIC_DIR / "index.html"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from calibrate_data import calibrate_cached_data
from game_engine import evaluate_roster, generate_game_teams, store

MAX_PAYLOAD_BYTES = 65536  # 64 KB max POST body size
DAILY_SYNC_INTERVAL_SECONDS = 86400  # 24 hours


def handle_get_health() -> dict:
    teams = store.get_teams()
    return {
        "status": "ok",
        "season": store.data.get("season", "2026/2027"),
        "teams_loaded": len(teams),
        "mode": "ultimate",
        "last_calibrated_utc": store.data.get("last_calibrated_utc"),
    }


def handle_get_teams() -> dict:
    """Returns masked teams only (never reveals ratings or leaderboards before draft ends)."""
    teams = store.get_teams()
    masked = {}
    for abbr, t in teams.items():
        masked[abbr] = {
            "id": t["id"],
            "abbr": t["abbr"],
            "name": t["name"],
            "short_name": t["short_name"],
            "location": t["location"],
            "nickname": t["nickname"],
            "color": t["color"],
            "alt_color": t["alt_color"],
            "logo": t.get("logo", ""),
            "record_2026": t.get("record_2026", ""),
            "players": [store.mask_player_for_draft(p, t) for p in t["players"]],
        }
    return {"teams": masked}


def handle_new_game(body: dict) -> dict:
    seed = body.get("seed")
    return generate_game_teams(seed_str=seed)


def handle_evaluate(body: dict) -> dict:
    drawn_teams = body.get("drawn_teams", [])
    picks = body.get("picks", [])
    session_token = body.get("session_token")
    return evaluate_roster(
        drawn_teams=drawn_teams,
        user_picks=picks,
        session_token=session_token,
    )


def handle_sync() -> dict:
    store.load_or_sync(force=True)
    calibrate_cached_data()
    store.load_or_sync(force=False)
    return {
        "status": "synced",
        "season": store.data.get("season", "2026/2027"),
        "teams_loaded": len(store.get_teams()),
        "last_calibrated_utc": store.data.get("last_calibrated_utc"),
    }


def is_authorized_sync_request(headers, client_ip: str) -> bool:
    """
    Protects /api/sync and /api/cron/sync from public abuse.
    Requires Authorization: Bearer <CRON_SECRET or SYNC_SECRET> in production,
    or allows loopback (127.0.0.1) only if no secret is configured locally.
    """
    secret = os.environ.get("CRON_SECRET") or os.environ.get("SYNC_SECRET")
    auth_header = headers.get("Authorization", "")
    if secret:
        expected = f"Bearer {secret}"
        return hmac.compare_digest(auth_header, expected)
    # Local fallback: only allow localhost if not running on Vercel
    if os.environ.get("VERCEL"):
        return False
    return client_ip in ("127.0.0.1", "::1", "localhost")


def start_daily_sync_scheduler() -> None:
    """Background daemon thread that refreshes NFL data once every 24 hours."""
    def _worker() -> None:
        while True:
            try:
                synced = store.sync_if_stale(max_age_hours=24.0)
                if synced:
                    print("[DailySync] Automatic 24h NFL data sync completed.")
            except Exception as exc:
                print(f"[DailySync] Error in background sync loop: {exc}")
            time.sleep(3600)  # Check once per hour if cache is >24h old

    t = threading.Thread(target=_worker, name="NFLDailySyncWorker", daemon=True)
    t.start()


class NFLAPIHandler(BaseHTTPRequestHandler):
    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, status_code: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(raw)

    def _send_bytes(self, status_code: int, content_type: str, data: bytes) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_security_headers()
        self.end_headers()

    def _resolve_request_path(self) -> str:
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if "__path" in qs and qs["__path"]:
            p = qs["__path"][0]
            return p if p.startswith("/") else f"/{p}"
        forwarded = (
            self.headers.get("x-vercel-original-path")
            or self.headers.get("x-Original-URL")
            or self.headers.get("x-rewrite-url")
        )
        if forwarded:
            return urlparse(forwarded).path
        return parsed.path

    def do_GET(self) -> None:
        path = self._resolve_request_path()
        try:
            if path == "/api/health":
                self._send_json(200, handle_get_health())
            elif path == "/api/teams":
                self._send_json(200, handle_get_teams())
            elif path == "/api/cron/sync":
                client_ip = self.client_address[0] if self.client_address else ""
                if not is_authorized_sync_request(self.headers, client_ip):
                    self._send_json(401, {"error": "Unauthorized cron request."})
                    return
                self._send_json(200, handle_sync())
            elif path.startswith("/api/"):
                self._send_json(404, {"error": f"API route not found: {path}"})
            else:
                # Serve static frontend files (index.html, /assets/*)
                rel = path.lstrip("/") or "index.html"
                candidate = (STATIC_DIR / rel).resolve()
                if (
                    candidate.is_file()
                    and str(candidate).startswith(str(STATIC_DIR.resolve()))
                ):
                    ctype, _ = mimetypes.guess_type(str(candidate))
                    self._send_bytes(200, ctype or "application/octet-stream", candidate.read_bytes())
                elif STATIC_HTML.exists():
                    self._send_bytes(200, "text/html; charset=utf-8", STATIC_HTML.read_bytes())
                else:
                    self._send_json(200, handle_get_health())
        except Exception as e:
            traceback.print_exc()
            self._send_json(500, {"error": str(e)})

    def do_POST(self) -> None:
        path = self._resolve_request_path()
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length header."})
            return

        if length > MAX_PAYLOAD_BYTES:
            self._send_json(413, {"error": "Payload too large (max 64 KB)."})
            return

        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw_body) if raw_body.strip() else {}
            if path == "/api/game/new":
                self._send_json(200, handle_new_game(body))
            elif path == "/api/game/evaluate":
                self._send_json(200, handle_evaluate(body))
            elif path in ("/api/sync", "/api/cron/sync"):
                client_ip = self.client_address[0] if self.client_address else ""
                if not is_authorized_sync_request(self.headers, client_ip):
                    self._send_json(401, {"error": "Unauthorized sync request."})
                    return
                self._send_json(200, handle_sync())
            else:
                self._send_json(404, {"error": f"Not found: {path}"})
        except ValueError as ve:
            self._send_json(400, {"error": str(ve)})
        except Exception as e:
            traceback.print_exc()
            self._send_json(500, {"error": "Internal server error."})

    def log_message(self, format: str, *args) -> None:
        sys.stdout.write(f"[NFL-17-0] {self.address_string()} - {format % args}\n")


def run_server(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = False) -> None:
    port = int(os.environ.get("PORT", port))
    start_daily_sync_scheduler()
    url = f"http://{host}:{port}"
    server = ThreadingHTTPServer((host, port), NFLAPIHandler)
    print("============================================================")
    print(" NFL Build A 17-0 Team (Ultimate Mode • 2026/2027) läuft auf:")
    print(f" -> {url}")
    print(" -> 1x täglicher Hintergrund-Sync aktiv (24h Intervall)")
    print("============================================================")

    if open_browser:
        def _open():
            time.sleep(0.4)
            print(f"Öffne {url} im Standard-Browser...")
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer wird beendet...")
        server.server_close()


if __name__ == "__main__":
    should_open = "--open" in sys.argv or "-o" in sys.argv
    run_server(open_browser=should_open)
