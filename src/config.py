# src/config.py
import os
from pathlib import Path

# Prefer importing find_dotenv/load_dotenv for robust discovery
try:
    from dotenv import load_dotenv, find_dotenv
except Exception:
    load_dotenv = None
    find_dotenv = None

def _load_dotenv_verbose():
    # Try to find .env in current working dir or parent dirs
    if find_dotenv and load_dotenv:
        env_path = find_dotenv(raise_error_if_not_found=False)
        if env_path:
            loaded = load_dotenv(env_path, override=False)
            print(f"[CONFIG] Loaded .env from: {env_path} (loaded={loaded})")
            return Path(env_path)
        else:
            # Try some likely locations relative to this file
            here = Path(__file__).resolve().parent.parent  # project root assuming src/ is inside project
            candidate = here / ".env"
            if candidate.exists():
                loaded = load_dotenv(str(candidate), override=False)
                print(f"[CONFIG] Loaded .env from project root: {candidate} (loaded={loaded})")
                return candidate
            print("[CONFIG] No .env found by dotenv. Continuing — environment variables may be empty.")
            return None
    else:
        print("[CONFIG] python-dotenv not installed or not available. Relying on actual environment variables.")
        return None

# Attempt to load .env and print where it was loaded from (if any)
_env_path = _load_dotenv_verbose()

# Now read values (strip to remove stray whitespace/newlines)
RUT = os.environ.get("RUT", "").strip()
# accept both uppercase and capitalized Clave
CLAVE = os.environ.get("CLAVE", os.environ.get("Clave", "")).strip()

# CFE filter defaults (DD/MM/YYYY)
ECF_TIPO = os.environ.get("ECF_TIPO", "111").strip()
ECF_FROM_DATE = os.environ.get("ECF_FROM_DATE", "01/06/2025").strip()
ECF_TO_DATE = os.environ.get("ECF_TO_DATE", "30/08/2025").strip()

# Timeouts (ms) - safe casting
def _to_int_env(key, default):
    try:
        return int(os.environ.get(key, default))
    except Exception:
        try:
            return int(default)
        except Exception:
            return 60000

GOTO_TIMEOUT = _to_int_env("GOTO_TIMEOUT_MS", 120000)
LOADSTATE_TIMEOUT = _to_int_env("LOADSTATE_TIMEOUT_MS", 60000)

# Final quick debug print (repr shows empty vs whitespace)
print("[CONFIG] RUT (repr):", repr(RUT))
print("[CONFIG] CLAVE (repr):", repr(CLAVE))
