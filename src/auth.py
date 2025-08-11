# src/auth.py
import time, traceback
from playwright.sync_api import TimeoutError, Error
from src import selectors as sel
from src import config

def _dump_debug(page, prefix="debug"):
    try:
        ts = int(time.time())
        page.screenshot(path=f"{prefix}_{ts}.png", full_page=True)
        with open(f"{prefix}_{ts}.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"[DEBUG] Saved debug files: {prefix}_{ts}.png and .html")
    except Exception as e:
        print("[DEBUG] Could not save debug files:", e)

def login_and_continue(page):
    try:
        print("[INFO] Waiting for page to load (networkidle)...")
        page.wait_for_load_state("networkidle", timeout=60000)

        target = None

        # Try main-page selectors first
        try:
            print("[INFO] Checking for main-page username input...")
            page.wait_for_selector(sel.USERNAME_INPUT, timeout=8000)
            target = page
            print("[INFO] Found main page login inputs.")
        except TimeoutError:
            print("[INFO] Main page inputs not found, checking for iframe...")
            iframe_el = page.query_selector('iframe[src*="loginProd"]') or page.query_selector("iframe")
            if iframe_el:
                frame = iframe_el.content_frame()
                if frame:
                    target = frame
                    print("[INFO] Using iframe as target:", frame.url)
            if not target:
                raise Exception("Login inputs not found on main page or in iframe.")

        # Fill username and password
        print("[INFO] Filling username...")
        target.fill(sel.USERNAME_INPUT, str(config.RUT))

        print("[INFO] Filling password...")
        target.fill(sel.PASSWORD_INPUT, str(config.CLAVE))

        # Click login button
        print("[INFO] Clicking login button...")
        if target.query_selector(sel.LOGIN_BUTTON_IMG):
            target.click(sel.LOGIN_BUTTON_IMG)
        elif target.query_selector('input[type="submit"]'):
            target.click('input[type="submit"]')
        elif target.query_selector('button[type="submit"]'):
            target.click('button[type="submit"]')
        else:
            target.click('button:has-text("Ingresar")')

        # Optional Continue button
        try:
            target.wait_for_selector(sel.CONTINUE_BUTTON, timeout=4000)
            print("[INFO] Clicking Continue...")
            target.click(sel.CONTINUE_BUTTON)
        except TimeoutError:
            print("[INFO] No Continue button found.")

        print("[SUCCESS] Login attempt completed.")
    except Error as e:
        print("[ERROR] Playwright error:", e)
        traceback.print_exc()
        _dump_debug(page)
        raise
    except Exception as e:
        print("[ERROR]", e)
        traceback.print_exc()
        _dump_debug(page)
        raise
