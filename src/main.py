# src/main.py
import time
from playwright.sync_api import sync_playwright
from src.auth import login_and_continue, fill_cfe_and_consult
from src import config

START_URL = "https://servicios.dgi.gub.uy/serviciosenlinea"

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("[INFO] Opening page...")
        page.goto(START_URL, wait_until="load", timeout=config.GOTO_TIMEOUT)

        # 1) Login + Continue + Nav to "Consulta de CFE recibidos"
        page_obj, url = login_and_continue(page, post_click_wait=5)
        print("[INFO] Landed at:", url)

        # 2) Fill CFE filters and click Consultar (values from .env/config)
        final_page, result_url = fill_cfe_and_consult(page_obj)
        print("[INFO] After consult, landed at:", result_url)

        # 3) (Optional) scrape results here

        print("[INFO] Done. Keeping browser open for 8 seconds to inspect...")
        time.sleep(8)

        context.close()
        browser.close()

if __name__ == "__main__":
    main()
