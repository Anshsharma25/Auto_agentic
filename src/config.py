# src/config.py
import os
from pathlib import Path

try:
    from dotenv import load_dotenv, find_dotenv
except Exception:
    load_dotenv = None
    find_dotenv = None

def _load_dotenv_verbose():
    if find_dotenv and load_dotenv:
        env_path = find_dotenv(raise_error_if_not_found=False)
        if env_path:
            loaded = load_dotenv(env_path, override=False)
            print(f"[CONFIG] Loaded .env from: {env_path} (loaded={loaded})")
            return Path(env_path)
        else:
            here = Path(__file__).resolve().parent.parent
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

_env_path = _load_dotenv_verbose()

RUT = os.environ.get("RUT", "").strip()
CLAVE = os.environ.get("CLAVE", os.environ.get("Clave", "")).strip()

ECF_TIPO = os.environ.get("ECF_TIPO", "111").strip()
ECF_FROM_DATE = os.environ.get("ECF_FROM_DATE", "01/06/2025").strip()
ECF_TO_DATE = os.environ.get("ECF_TO_DATE", "30/08/2025").strip()

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

print("[CONFIG] RUT (repr):", repr(RUT))
print("[CONFIG] CLAVE (repr):", repr(CLAVE))
