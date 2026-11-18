"""
MT5 connection diagnostic — run this from cmd/PowerShell to see what's happening.
"""
import os, sys, subprocess

print("=" * 60)
print("MT5 DIAGNOSTIC")
print("=" * 60)

# 1. Which MT5 terminals are on disk?
paths = [
    r"C:\Program Files\MetaTrader 5 Terminal\terminal64.exe",
    r"C:\Program Files\MetaTrader 5\terminal64.exe",
    r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
]
print("\n[1] MT5 executables on disk:")
for p in paths:
    exists = os.path.exists(p)
    if exists:
        mtime = os.path.getmtime(p)
        import datetime
        dt = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        print(f"  FOUND  {p}  (modified {dt})")
    else:
        print(f"  missing {p}")

# 2. Which MT5 processes are running?
print("\n[2] Running MT5 processes:")
try:
    out = subprocess.check_output(
        ["wmic", "process", "where", "name='terminal64.exe'",
         "get", "ProcessId,ExecutablePath"],
        text=True, stderr=subprocess.DEVNULL
    )
    print(out.strip() or "  (none found)")
except Exception as e:
    print(f"  wmic failed: {e}")

# 3. MT5 Python library version
print("\n[3] MetaTrader5 Python library:")
try:
    import MetaTrader5 as mt5
    print(f"  version: {mt5.__version__}")
except ImportError:
    print("  NOT INSTALLED — run:  pip install MetaTrader5")
    sys.exit(1)

# 4. Try initialize without any args (auto-detect running terminal)
print("\n[4] mt5.initialize()  — auto-detect, no args:")
ok = mt5.initialize()
print(f"  result: {ok}   error: {mt5.last_error()}")
if ok:
    info = mt5.terminal_info()
    print(f"  terminal: {info.path}")
    print(f"  build:    {info.build}")
    print(f"  connected:{info.connected}")
    mt5.shutdown()

# 5. Try each known path
for p in paths:
    if not os.path.exists(p):
        continue
    print(f"\n[5] mt5.initialize(path=r'{p}'):")
    mt5.shutdown()
    ok = mt5.initialize(path=p)
    print(f"  result: {ok}   error: {mt5.last_error()}")
    if ok:
        info = mt5.terminal_info()
        print(f"  build: {info.build}  connected: {info.connected}")
        mt5.shutdown()
        break

print("\n[6] Done.")
