
import os
from pathlib import Path
from dotenv import load_dotenv

# load .env if present
env_path = Path('.') / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

RUT = os.getenv('RUT')
CLAVE = os.getenv('CLAVE')
ECF_TIPO = os.getenv('ECF_TIPO', '111')
ECF_FROM_DATE = os.getenv('ECF_FROM_DATE', '')
ECF_TO_DATE = os.getenv('ECF_TO_DATE', '')
DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR', 'downloads')
OUTPUT_FILE = os.getenv('OUTPUT_FILE', 'outputs/cfe_data.xlsx')
HEADLESS = os.getenv('HEADLESS', 'true').lower() in ('1', 'true', 'yes')

# small validation
if not RUT or not CLAVE:
    print('[WARN] RUT or CLAVE not set in environment; make sure .env has values')