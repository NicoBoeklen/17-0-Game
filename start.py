"""
One-Click Launcher für NFL Build A 17-0 Team (Saison 2026/2027).
Startet den lokalen Server auf http://127.0.0.1:8000 und öffnet das Spiel direkt im Browser.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))
from server import run_server

if __name__ == "__main__":
    run_server(host="127.0.0.1", port=8000, open_browser=True)
