# src/auth.py
import time
import traceback
from typing import Optional, Tuple
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

def _find_continue_element(page, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            el = page.query_selector(sel.CONTINUE_BUTTON)
            if el:
                try:
                    el.scroll_into_view_if_needed()
                except Exception:
                    pass
                return el
        except Exception:
            pass

        try:
            for frame in page.frames:
                try:
                    fel = frame.query_selector(sel.CONTINUE_BUTTON)
                    if fel:
                        try:
                            fel.scroll_into_view_if_needed()
                        except Exception:
                            pass
                        return fel
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.5)
    return None

def login_and_continue(page, post_click_wait: int = 5, wait_for_selector: Optional[str] = None) -> Tuple[object, str]:
    """
    Login, click continue, then click 'Consulta de CFE recibidos' link,
    wait for navigation after each click, then return final page and url.
    """
    try:
        print("[INFO] Waiting for initial page load (networkidle)...")
        try:
            page.wait_for_load_state("networkidle", timeout=60000)
        except Exception:
            try:
                page.wait_for_load_state("load", timeout=30000)
            except Exception:
                print("[WARN] Initial page did not reach networkidle/load in time, continuing...")

        target = None

        try:
            print("[INFO] Looking for username input on main page...")
            page.wait_for_selector(sel.USERNAME_INPUT, timeout=8000)
            target = page
            print("[INFO] Found main page login inputs.")
        except TimeoutError:
            print("[INFO] Main page inputs not found; checking iframe...")
            iframe_el = page.query_selector('iframe[src*="loginProd"]') or page.query_selector("iframe")
            if iframe_el:
                frame = iframe_el.content_frame()
                if frame:
                    target = frame
                    print("[INFO] Using iframe as target:", getattr(frame, "url", "<frame>"))
            if not target:
                raise Exception("Login inputs not found on main page or in iframe.")

        print("[INFO] Filling username...")
        target.fill(sel.USERNAME_INPUT, str(config.RUT))
        print("[INFO] Filling password...")
        target.fill(sel.PASSWORD_INPUT, str(config.CLAVE))

        print("[INFO] Clicking login button...")
        if target.query_selector(sel.LOGIN_BUTTON_IMG):
            target.click(sel.LOGIN_BUTTON_IMG)
        elif target.query_selector('input[type="submit"]'):
            target.click('input[type="submit"]')
        elif target.query_selector('button[type="submit"]'):
            target.click('button[type="submit"]')
        else:
            target.click('button:has-text("Ingresar")')

        print("[INFO] Waiting for 'selecciona-entidad' in URL (up to 60s)...")
        reached = _wait_for_url_contains(page, "selecciona-entidad", timeout=60)
        print(f"[DEBUG] URL after login attempt: {page.url}")
        if not reached:
            print("[WARN] 'selecciona-entidad' not seen; will still look for Continue button.")

        print("[INFO] Searching for Continue button (up to 30s)...")
        cont_el = _find_continue_element(page, timeout=30)
        if not cont_el:
            print("[WARN] Continue button not found. Dumping debug and returning current page.")
            _dump_debug(page)
            return page, page.url

        final_page = page
        final_url = page.url

        print("[INFO] Continue button found. Clicking it now...")
        try:
            with page.context.expect_page(timeout=5000) as new_page_ctx:
                cont_el.click()
            new_page = new_page_ctx.value
            print("[INFO] New page/tab detected after click. Waiting for load...")
            try:
                new_page.wait_for_load_state("load", timeout=30000)
            except Exception:
                try:
                    new_page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    pass
            final_page = new_page
            final_url = new_page.url
            print(f"[INFO] Landed on new page/tab: {final_url}")
        except TimeoutError:
            print("[DEBUG] No new tab detected; waiting for navigation/load on same page...")
            try:
                page.wait_for_navigation(timeout=30000)
                final_page = page
                final_url = page.url
                print(f"[INFO] Same-page navigation detected. URL: {final_url}")
            except Exception:
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    try:
                        page.wait_for_load_state("load", timeout=15000)
                    except Exception:
                        print("[WARN] Page did not reach stable load state after Continue click.")
                final_page = page
                final_url = page.url
                print(f"[INFO] After fallback waits, URL is: {final_url}")

        if wait_for_selector:
            print(f"[INFO] Waiting for selector '{wait_for_selector}' on final page (timeout {post_click_wait}s)...")
            try:
                final_page.wait_for_selector(wait_for_selector, timeout=post_click_wait*1000)
                print("[INFO] Selector appeared on final page.")
            except Exception:
                print("[WARN] Selector did not appear within timeout; proceeding.")
        else:
            print(f"[INFO] Sleeping {post_click_wait}s on final page...")
            time.sleep(post_click_wait)

        # Now click on "Consulta de CFE recibidos" link and wait for navigation
        print("[INFO] Clicking 'Consulta de CFE recibidos' link...")
        with final_page.expect_navigation(timeout=30000):
            final_page.click('text="Consulta de CFE recibidos"')
        final_url = final_page.url
        print(f"[INFO] Landed on page after clicking 'Consulta de CFE recibidos': {final_url}")

        # Optionally wait here again or sleep if needed
        time.sleep(3)  # wait 3 seconds on this new page

        print("[SUCCESS] Navigation complete. Ready on final page.")
        return final_page, final_url

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
