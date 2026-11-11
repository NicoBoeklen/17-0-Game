"""
Vercel Python Serverless Function Entrypoint for Build A 17-0 Team.
Routes all /api/* requests (including /api/game/new, /api/game/evaluate,
/api/health, and the daily Vercel Cron /api/cron/sync) to NFLAPIHandler.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from server import NFLAPIHandler


class handler(NFLAPIHandler):
    """Vercel Python Runtime handler class."""
    pass
