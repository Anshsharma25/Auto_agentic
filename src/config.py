# src/config.py
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Credentials
RUT = os.environ.get("RUT", "")
CLAVE = os.environ.get("CLAVE", "")

# CFE filter defaults (DD/MM/YYYY)
ECF_TIPO = os.environ.get("ECF_TIPO", "111")           # 111 => e-Factura
ECF_FROM_DATE = os.environ.get("ECF_FROM_DATE", "01/06/2025")
ECF_TO_DATE = os.environ.get("ECF_TO_DATE", "30/08/2025")

# Timeouts (ms)
GOTO_TIMEOUT = int(os.environ.get("GOTO_TIMEOUT_MS", "120000"))
LOADSTATE_TIMEOUT = int(os.environ.get("LOADSTATE_TIMEOUT_MS", "60000"))
