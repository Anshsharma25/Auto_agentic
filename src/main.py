# src/main.py
from playwright.sync_api import sync_playwright
from src.auth import login_and_continue

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("[INFO] Opening page...")
        page.goto("https://servicios.dgi.gub.uy/serviciosenlinea", wait_until="networkidle", timeout=60000)

        login_and_continue(page)

        print("[INFO] Done. Keeping browser open for 5 seconds...")
        page.wait_for_timeout(5000)
        browser.close()

if __name__ == "__main__":
    main()
