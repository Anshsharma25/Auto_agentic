# src/main.py
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from src.auth import login_and_continue, fill_cfe_and_consult, export_xls_and_save
from src import config

START_URL = "https://servicios.dgi.gub.uy/serviciosenlinea"

def main():
    print("[CONFIG] LOGIN START URL:", START_URL)
    print("[CONFIG] GOTO_TIMEOUT (ms):", config.GOTO_TIMEOUT)
    print("[CONFIG] RUT (repr):", repr(config.RUT))
    print("[CONFIG] CLAVE (repr):", repr(config.CLAVE))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True, ignore_https_errors=True)
        page = context.new_page()

        print("[INFO] Opening page...")
        try:
            page.goto(START_URL, wait_until="load", timeout=config.GOTO_TIMEOUT)
        except Exception:
            try:
                page.goto(START_URL, wait_until="domcontentloaded", timeout=config.GOTO_TIMEOUT)
            except Exception as e:
                print("[WARN] Could not fully navigate to start URL:", e)

        # 1) Login + Continue + Nav to "Consulta de CFE recibidos"
        page_obj, url = login_and_continue(page, post_click_wait=5)
        print("[INFO] Landed at:", url)

        # 2) Fill CFE filters and click Consultar (values from .env/config)
        final_page, result_url = fill_cfe_and_consult(page_obj)
        print("[INFO] After consult, landed at:", result_url)

        # 3) Export XLS by clicking the highlighted control and save it
        downloads_dir = Path.cwd() / "downloads"
        saved_path = export_xls_and_save(final_page, save_dir=str(downloads_dir), timeout=30000)
        if saved_path:
            print(f"[INFO] Export saved to: {saved_path}")
        else:
            print("[ERROR] Export failed or file not found.")

        print("[INFO] Done. Keeping browser open for 5 seconds to inspect...")
        time.sleep(5)

        context.close()
        browser.close()

if __name__ == "__main__":
    main()
# python -m src.main
