# src/config.py
import os
from dotenv import load_dotenv

load_dotenv()

RUT = os.getenv("RUT")
CLAVE = os.getenv("Clave") or os.getenv("CLAVE") or os.getenv("PASSWORD") or os.getenv("PASS")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")

if not RUT or not CLAVE:
    raise ValueError("Please set RUT and Clave in .env file")

# Example .env file:
# RUT=213624850018
# Clave=aa0000aa
# DOWNLOAD_DIR=./downloads
