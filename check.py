import os, time, json
from datetime import date

LOG_DIR     = "logs"
STATE_FILE  = "logs/loss_detector_state.json"
SIGNAL_FILE = "logs/latest_signals.json"

print("=== CHECKING BOT FILES ===")

if os.path.exists(STATE_FILE):
    state = json.load(open(STATE_FILE, encoding="utf-8"))
    print("State file: FOUND | Status:", state.get("status"))
else:
    print("State file: MISSING")

today    = date.today().strftime("%Y%m%d")
log_file = os.path.join(LOG_DIR, f"bot_{today}.log")

if os.path.exists(log_file):
    age = time.time() - os.path.getmtime(log_file)
    print("Log file:   FOUND | Age:", round(age), "seconds | Alive:", age < 600)
else:
    print("Log file:   MISSING -", log_file)

if os.path.exists(SIGNAL_FILE):
    age = time.time() - os.path.getmtime(SIGNAL_FILE)
    print("Signal file: FOUND | Age:", round(age), "seconds | Alive:", age < 600)
else:
    print("Signal file: MISSING")

print("=== DONE ===")