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

# ---------------------------
# Appended helpers & robust fill + consult functions
# ---------------------------

def _click_maybe_in_frames(page, selector, timeout=2000):
    """
    Try click on main page first; otherwise try frames.
    """
    try:
        page.click(selector, timeout=timeout)
        return True
    except Exception:
        for frame in page.frames:
            try:
                frame.click(selector, timeout=timeout)
                return True
            except Exception:
                continue
    return False

def _find_element_in_page_and_frames(page, selector, timeout=5000):
    """
    Return tuple (frame_or_page, element_handle) where frame_or_page is page (main) or a Frame object.
    Logs where it found the element. Returns (None, None) if not found.
    """
    deadline = time.time() + (timeout / 1000)
    while time.time() < deadline:
        # main frame (page)
        try:
            el = page.query_selector(selector)
            if el:
                print(f"[DEBUG] Found selector '{selector}' on main page")
                return page, el
        except Exception:
            pass
        # child frames
        try:
            for frame in page.frames:
                try:
                    el = frame.query_selector(selector)
                    if el:
                        print(f"[DEBUG] Found selector '{selector}' in frame: {getattr(frame, 'url', '<frame>')}")
                        return frame, el
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.2)
    print(f"[DEBUG] Selector '{selector}' not found in page or frames within timeout")
    return None, None

def _set_select_value(frame_or_page, element_handle, value):
    """
    Try multiple ways to set select value:
      1) frame_or_page.select_option
      2) element_handle.evaluate to set .value and dispatch events + call gx handlers
      3) click/select + click option fallback
    Returns True if succeeded.
    """
    # 1) try select_option on frame_or_page
    try:
        frame_or_page.select_option(sel.SELECT_TIPO_CFE, value)
        print("[DEBUG] select_option succeeded.")
        return True
    except Exception:
        pass

    # 2) try element_handle.evaluate to set value and dispatch events
    try:
        element_handle.evaluate(
            """(el, val) => {
                el.value = val;
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
                el.dispatchEvent(new Event('blur', {bubbles:true}));
                try { if (window.gx && gx.evt && typeof gx.evt.onchange === 'function') gx.evt.onchange(el); } catch(e){}
                try { if (window.gx && gx.evt && typeof gx.evt.onblur === 'function') gx.evt.onblur(el); } catch(e){}
                return true;
            }""",
            value
        )
        print("[DEBUG] element_handle.evaluate set select value.")
        return True
    except Exception as e:
        print("[DEBUG] element_handle.evaluate for select failed:", e)

    # 3) fallback: click select then try to click option element
    try:
        element_handle.click()
        try:
            frame_or_page.click(f'{sel.SELECT_TIPO_CFE} >> option[value="{value}"]', timeout=2000)
            print("[DEBUG] clicked option fallback succeeded.")
            return True
        except Exception:
            pass
    except Exception:
        pass

    return False

def _set_input_value_with_fallback(frame_or_page, element_handle, value):
    """
    Try to set input value:
      1) element_handle.evaluate to set .value + dispatch events + run gx.date.valid_date
      2) typing fallback: click and type char-by-char (for masked inputs)
    Returns True if succeeded.
    """
    # 1) Try evaluate on the element handle
    try:
        element_handle.evaluate(
            """(el, val) => {
                try { el.focus && el.focus(); } catch(e) {}
                el.value = val;
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
                el.dispatchEvent(new Event('blur', {bubbles:true}));
                try { if (window.gx && gx.evt && typeof gx.evt.onchange === 'function') gx.evt.onchange(el); } catch(e){}
                try { if (window.gx && gx.date && typeof gx.date.valid_date === 'function') {
                    try { gx.date.valid_date(el, 10, 'DMY', 0, 24, 'spa', false, 0); } catch(e){}
                } } catch(e) {}
                return true;
            }""",
            value
        )
        print("[DEBUG] element_handle.evaluate set input value.")
        return True
    except Exception as e:
        print("[DEBUG] element_handle.evaluate for input failed:", e)

    # 2) Typing fallback: click element and type char by char
    try:
        element_handle.click(timeout=2000)
        time.sleep(0.2)
        for ch in value:
            element_handle.type(ch, delay=80)
        try:
            element_handle.evaluate("(el) => { el.dispatchEvent(new Event('blur', {bubbles:true})); }")
        except Exception:
            pass
        print("[DEBUG] typing fallback succeeded for input.")
        return True
    except Exception as e:
        print("[DEBUG] typing fallback failed for input:", e)

    return False

def fill_cfe_and_consult(
    page,
    tipo_value: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    wait_after_result: int = 3
) -> Tuple[object, str]:
    """
    After landing on the "Consulta de CFE recibidos" page, set the tipo, dates,
    and click Consultar. Returns (final_page, final_url).
    If arguments are None, values are taken from src.config.
    """
    try:
        tipo = tipo_value or getattr(config, "ECF_TIPO", "111")
        d_from = date_from or getattr(config, "ECF_FROM_DATE", "")
        d_to = date_to or getattr(config, "ECF_TO_DATE", "")

        print(f"[INFO] fill_cfe_and_consult: tipo={tipo}, desde={d_from}, hasta={d_to}")

        # 1) Set select
        frame, el = _find_element_in_page_and_frames(page, sel.SELECT_TIPO_CFE, timeout=5000)
        if el:
            try:
                ok = _set_select_value(frame, el, tipo)
                if ok:
                    print("[INFO] vFILTIPOCFE set.")
                else:
                    print("[WARN] Could not set vFILTIPOCFE by any method.")
            except Exception as e:
                print("[ERROR] Exception while setting vFILTIPOCFE:", e)
        else:
            print("[WARN] Select vFILTIPOCFE not found - cannot set.")

        # 2) Fill 'desde' input
        if d_from:
            frame_from, el_from = _find_element_in_page_and_frames(page, sel.DATE_FROM, timeout=5000)
            if el_from:
                ok = _set_input_value_with_fallback(frame_from, el_from, d_from)
                if ok:
                    print("[INFO] CTLFECHADESDE set.")
                else:
                    print("[WARN] Could not set CTLFECHADESDE by any method.")
            else:
                print("[WARN] CTLFECHADESDE not found on page/frames.")

        # 3) Fill 'hasta' input
        if d_to:
            frame_to, el_to = _find_element_in_page_and_frames(page, sel.DATE_TO, timeout=5000)
            if el_to:
                ok = _set_input_value_with_fallback(frame_to, el_to, d_to)
                if ok:
                    print("[INFO] CTLFECHAHASTA set.")
                else:
                    print("[WARN] Could not set CTLFECHAHASTA by any method.")
            else:
                print("[WARN] CTLFECHAHASTA not found on page/frames.")

        # small pause for client-side processing
        time.sleep(0.5)

        # 4) Click Consultar and wait for navigation/results
        print("[INFO] Clicking Consultar...")
        final_page = page
        final_url = page.url

        try:
            # prefer same-page navigation
            with page.expect_navigation(timeout=30000):
                clicked = _click_maybe_in_frames(page, sel.BUTTON_CONSULTAR)
                if not clicked:
                    raise Exception("Could not click Consultar (no element found).")
            final_page = page
            final_url = page.url
            print("[INFO] Navigation after Consultar done. URL:", final_url)
        except Exception:
            # maybe opens new tab
            try:
                with page.context.expect_page(timeout=5000) as new_page_ctx:
                    clicked = _click_maybe_in_frames(page, sel.BUTTON_CONSULTAR)
                    if not clicked:
                        raise Exception("Could not click Consultar (no element found).")
                new_page = new_page_ctx.value
                try:
                    new_page.wait_for_load_state("load", timeout=30000)
                except Exception:
                    try:
                        new_page.wait_for_load_state("networkidle", timeout=30000)
                    except Exception:
                        pass
                final_page = new_page
                final_url = new_page.url
                print("[INFO] Consultar opened new tab. URL:", final_url)
            except Exception:
                # final fallback: click and wait networkidle on same page
                clicked_any = _click_maybe_in_frames(page, sel.BUTTON_CONSULTAR)
                if not clicked_any:
                    print("[ERROR] Could not click Consultar anywhere. Dumping debug.")
                    _dump_debug(page)
                    return page, page.url
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    pass
                final_page = page
                final_url = page.url
                print("[INFO] After fallback click, URL:", final_url)

        # optional hold for final page to settle
        if wait_after_result and wait_after_result > 0:
            time.sleep(wait_after_result)

        print("[SUCCESS] fill_cfe_and_consult finished. Final URL:", final_url)
        return final_page, final_url

    except Exception as e:
        print("[ERROR] Exception in fill_cfe_and_consult:", e)
        traceback.print_exc()
        _dump_debug(page)
        raise

# ---------------------------
# New helper: click the image link inside iframe and open
# ---------------------------
def click_iframe_image_and_open(page, wait_seconds: int = 5):
    """
    Find an iframe whose src contains 'efacConsultasMenuServFE', switch to it,
    find the anchor/image link, click it, and return the opened page (new tab)
    or the same page if navigation happened in-place.
    """
    try:
        print("[INFO] Looking for efacConsultasMenuServFE iframe...")
        iframe_el = page.query_selector('iframe[src*="efacConsultasMenuServFE"]') or page.query_selector('iframe[id^="gxpea"]')
        if not iframe_el:
            # fallback: try ANY iframe and inspect urls
            for f in page.query_selector_all("iframe"):
                src = f.get_attribute("src") or ""
                if "efacConsultasMenuServFE" in src or "efacconsmnuservredireccion" in src:
                    iframe_el = f
                    break

        if not iframe_el:
            print("[ERROR] Target iframe not found on the page.")
            _dump_debug(page)
            return None

        frame = iframe_el.content_frame()
        if not frame:
            print("[ERROR] Could not access iframe content frame.")
            _dump_debug(page)
            return None

        print("[INFO] Got content frame. Looking for image/link inside frame...")

        # Try multiple selectors in order of likelihood
        selectors_to_try = [
            'a[href*="efacconsultatwebsobrecfe"]',
            'a:has(img[src*="K2BActionDisplay.gif"])',
            'a:has(img[id^="vCOLDISPLAY"])',
            'img[src*="K2BActionDisplay.gif"]',  # will click parent anchor if needed
            'img[id^="vCOLDISPLAY"]'
        ]

        anchor = None
        for selq in selectors_to_try:
            try:
                # If selector selects an <img>, find its closest <a>
                el = frame.query_selector(selq)
                if el:
                    if el.evaluate("el => el.tagName.toLowerCase()") == "img":
                        # find parent anchor
                        try:
                            parent = el.evaluate_handle("img => img.closest('a')")
                            if parent:
                                anchor = parent.as_element()
                        except Exception:
                            anchor = None
                    else:
                        anchor = el
                if anchor:
                    print(f"[DEBUG] Found element with selector: {selq}")
                    break
            except Exception:
                continue

        if not anchor:
            print("[ERROR] Could not find link/image inside iframe with known selectors.")
            _dump_debug(page)
            return None

        # Try clicking and detect whether it opens a new tab or navigates same page
        print("[INFO] Clicking the link inside iframe...")
        try:
            with page.context.expect_page(timeout=10000) as new_page_ctx:
                anchor.click()
            new_page = new_page_ctx.value
            try:
                new_page.wait_for_load_state("load", timeout=20000)
            except Exception:
                try:
                    new_page.wait_for_load_state("networkidle", timeout=20000)
                except Exception:
                    pass
            print("[SUCCESS] Link opened in a new tab:", new_page.url)
            return new_page
        except TimeoutError:
            # No new tab — maybe same-frame navigation
            try:
                anchor.click()
            except Exception as e:
                print("[WARN] click without new tab failed:", e)
            # give it some time to navigate or load content
            try:
                frame.wait_for_load_state("load", timeout=10000)
            except Exception:
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
            print("[INFO] Clicked link — no new tab detected. Current page URL:", page.url)
            # keep page visible for debugging/inspection
            time.sleep(wait_seconds)
            return page

    except Exception as e:
        print("[ERROR] Exception in click_iframe_image_and_open:", e)
        traceback.print_exc()
        _dump_debug(page)
        raise