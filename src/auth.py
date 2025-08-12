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

def _wait_for_url_contains(page, substring, timeout=60):
    """Poll page.url until substring present or timeout. Returns True if found."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            url = page.url
        except Exception:
            url = ""
        if substring in url:
            return True
        time.sleep(0.5)
    return False

def _find_and_click_continue(page, timeout=30):
    """
    Try to find the continue button on the main page or inside frames.
    Returns True if clicked.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        # Try main page
        try:
            el = page.query_selector(sel.CONTINUE_BUTTON)
            if el:
                try:
                    el.scroll_into_view_if_needed()
                except Exception:
                    pass
                try:
                    el.click()
                    return True
                except Exception as e:
                    # maybe not yet clickable
                    # continue to try frames as well
                    print("[DEBUG] Found continue on main page but click failed:", e)
        except Exception:
            pass

        # Try every frame
        try:
            for frame in page.frames:
                try:
                    fel = frame.query_selector(sel.CONTINUE_BUTTON)
                    if fel:
                        try:
                            fel.scroll_into_view_if_needed()
                        except Exception:
                            pass
                        try:
                            fel.click()
                            return True
                        except Exception as e:
                            print("[DEBUG] Found continue in frame but click failed:", e)
                except Exception:
                    continue
        except Exception:
            pass

        time.sleep(0.5)
    return False

def login_and_continue(page):
    try:
        print("[INFO] Waiting for page to load (networkidle)...")
        page.wait_for_load_state("networkidle", timeout=60000)

        target = None

        # Try main-page selectors first (or fallback to iframe)
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

        # Fill credentials
        print("[INFO] Filling username...")
        target.fill(sel.USERNAME_INPUT, str(config.RUT))
        print("[INFO] Filling password...")
        target.fill(sel.PASSWORD_INPUT, str(config.CLAVE))

        # Click login button (avoid expect_navigation to prevent hanging)
        print("[INFO] Clicking login button...")
        if target.query_selector(sel.LOGIN_BUTTON_IMG):
            target.click(sel.LOGIN_BUTTON_IMG)
        elif target.query_selector('input[type="submit"]'):
            target.click('input[type="submit"]')
        elif target.query_selector('button[type="submit"]'):
            target.click('button[type="submit"]')
        else:
            target.click('button:has-text("Ingresar")')

        # Wait (poll) until we reach the selecciona-entidad URL (or timeout)
        print("[INFO] Waiting for selecciona-entidad URL (up to 60s)...")
        reached = _wait_for_url_contains(page, "selecciona-entidad", timeout=60)
        current_url = page.url
        print(f"[DEBUG] Current URL after login: {current_url}")

        if not reached:
            print("[WARN] Did not detect 'selecciona-entidad' in URL within timeout. Will still try to find Continue button on current page(s).")

        # Try to find and click the Continue button (search main page and iframes)
        print("[INFO] Looking for Continue button (up to 30s)...")
        clicked = _find_and_click_continue(page, timeout=30)
        if clicked:
            # Wait for next page to load after clicking Continue
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                # fallback to DOMContentLoaded
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
            print(f"[DEBUG] Continue clicked, current URL: {page.url}")
        else:
            print("[WARN] Could not find or click the Continue button within timeout.")
            _dump_debug(page)

        print("[SUCCESS] Login + Continue attempt finished.")

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
