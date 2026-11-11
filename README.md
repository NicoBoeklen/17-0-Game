# Build A 17-0 Team (Ultimate 10-Slot • Saison 2026/2027)

Ein für **Handy & Laptop** optimiertes **17-0 Football Roster-Draft-Game** im exklusiven **Ultimate-Modus (10 Slots)** mit Daten der Saison 2026/2027, **Trench-basierter OL-Bewertung** (Pass Block Win Rate, Sack Rate & RB YPC statt Offense-Punkten), **HMAC Anti-Cheat-Validierung** und **Vercel Serverless Deployment**.

---

## 🚀 Lokal starten (1 Klick)

Das Spiel öffnet sich sofort unter **http://127.0.0.1:8000** im Browser (inkl. automatischem 24h Hintergrund-Sync):

- **Per Doppelklick im Explorer / CMD:** `start.bat`
- **Per PowerShell:** `.\start.ps1`
- **Per Python:** `python start.py`

---

## ☁️ Komplett Serverless auf Vercel deployen (Option B)

Das Projekt ist vollständig für **Vercel Serverless** (Frontend + Python Serverless API unter `/api/*` + täglicher Cron-Sync) vorkonfiguriert:

1. **Repository auf GitHub pushen** (inkl. `vercel.json`, `api/index.py`, `.github/workflows/daily_sync.yml`).
2. Auf [vercel.com/new](https://vercel.com/new) das GitHub-Repository importieren und auf **Deploy** klicken (keine weiteren Build-Einstellungen nötig – `vercel.json` erledigt alles automatisch).
3. **Optional (Empfohlen für Production Security):** In den Vercel Project Settings unter *Environment Variables* setzen:
   - `NFL170_SESSION_SECRET`: Beliebiger geheimer Zufallsstring für die HMAC-Signatur der gezogenen Teams.
   - `CRON_SECRET`: Geheimer String, mit dem Vercel den täglichen Cronjob `/api/cron/sync` authentifiziert.
4. **Automatischer 1× täglicher Daten-Sync:**
   - **Vercel Cron:** In `vercel.json` ist `/api/cron/sync` auf `0 6 * * *` (täglich 06:00 UTC) konfiguriert.
   - **GitHub Actions:** Zusätzlich aktualisiert `.github/workflows/daily_sync.yml` einmal täglich um 06:00 UTC die Datei `backend/data/nfl_live_data.json`.

---

## ✨ Features & Architektur

- **Exklusiver Ultimate-Modus (10 Slots):** `QB, RB1, RB2, WR1, WR2, TE1, TE2, OL, DEF, HC`.
- **Realistische OL-Gewichtung (Trench Metrics statt Offense-Punkte):**
  - Offensive Lines werden zu **52 % nach Pass Protection** (`Pass Block Win Rate %` & niedrige `Sack Rate Allowed %`) und zu **48 % nach Run Blocking** (`RB Yards Per Carry`, `RB Rush YPG` & `RB Rush TDs`) bewertet – komplett unabhängig von QB-Fantasy-Punkten oder Team-PPG.
- **Mobile-First & Laptop UX:**
  - Direkt sichtbare **Open-Slots-Filterleiste** mit Live-Counter der noch offenen Positionen.
  - Sofort sichtbare Starter-Karten pro Runde ohne versteckte Popover.
- **Marken- & Bildrechtskonform (Trademark-Safe):**
  - Rendert dynamische Team-Embleme und Trikotnummer-Avatare in den Teamfarben ohne externe ESPN-Spielerfotos oder geschützte NFL-Vektorlogos, inklusive klarem Fair-Use-Disclaimer im Footer.
- **Gehärtete API & Anti-Cheat:**
  - `HMAC-SHA256` Session-Token verhindert das Manipulieren gezogener Teams oder Runden-Picks.
  - Payload-Limit (`64 KB`), Security-Header und geschützter `/api/cron/sync`-Endpunkt.
