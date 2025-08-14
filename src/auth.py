# src/auth.py
import time
import traceback
import os
import re
import urllib.parse
import csv
from datetime import datetime
from typing import Optional, Tuple, List
import pandas as pd
from playwright.sync_api import TimeoutError, Error

from src import selectors as sel
from src import config

# ---------------------------
# Debug / wait helpers
# ---------------------------
def _dump_debug(page, prefix="debug"):
    try:
        ts = int(time.time())
        out_png = f"{prefix}_{ts}.png"
        out_html = f"{prefix}_{ts}.html"
        page.screenshot(path=out_png, full_page=True)
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"[DEBUG] Saved debug files: {out_png} and {out_html}")
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

# ---------------------------
# URL helpers & incremental persistence
# ---------------------------

def _canonicalize_url(url: str) -> str:
    """Normalize a URL for deduplication. Removes fragment, normalizes scheme/netloc casing and strips trailing slash."""
    if not url:
        return ""
    try:
        p = urllib.parse.urlparse(url)
        path = urllib.parse.urljoin('/', p.path)  # normalizes path
        path = path.rstrip('/')
        canon = urllib.parse.urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", p.query or "", ""))
        return canon
    except Exception:
        return url.strip()


def _append_row_to_csv(csv_path: str, row: dict, fieldnames: list):
    """Append a row to CSV (creates file + header if missing)."""
    write_header = not os.path.exists(csv_path)
    out_dir = os.path.dirname(csv_path) or "."
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------
# Login / Continue helpers
# (UNCHANGED from your original file)
# ---------------------------
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
    Login to the site, press Continue and then click the 'Consulta de CFE recibidos' entry.
    Returns (final_page, final_url).
    """
    try:
        print("[INFO] Waiting for initial page load (networkidle)...")
        try:
            page.wait_for_load_state("networkidle", timeout=60000)
        except Exception:
            try:
                page.wait_for_load_state("load", timeout=30000)
            except Exception:
                print("[WARN] initial load didn't reach networkidle/load - continuing")

        target = None
        try:
            print("[INFO] Looking for username input on main page...")
            page.wait_for_selector(sel.USERNAME_INPUT, timeout=8000)
            target = page
            print("[INFO] Found main page login inputs.")
        except TimeoutError:
            print("[INFO] Main page inputs not found; trying iframe...")
            iframe_el = page.query_selector('iframe[src*="loginProd"]') or page.query_selector("iframe")
            if iframe_el:
                frame = iframe_el.content_frame()
                if frame:
                    target = frame
                    print("[INFO] Using iframe as target for login.")
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
            print("[WARN] 'selecciona-entidad' not observed; will still search for Continue button.")

        cont_el = _find_continue_element(page, timeout=30)
        if not cont_el:
            print("[WARN] Continue button not found. Dumping debug and returning current page.")
            _dump_debug(page)
            return page, page.url

        final_page = page
        final_url = page.url

        print("[INFO] Clicking Continue...")
        try:
            with page.context.expect_page(timeout=5000) as new_page_ctx:
                cont_el.click()
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
            print("[INFO] Landed on new tab after Continue:", final_url)
        except TimeoutError:
            print("[DEBUG] No new tab; waiting for same-page navigation...")
            try:
                page.wait_for_navigation(timeout=30000)
                final_page = page
                final_url = page.url
            except Exception:
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    pass
                final_page = page
                final_url = page.url
            print("[INFO] After Continue (same page):", final_url)

        if wait_for_selector:
            try:
                final_page.wait_for_selector(wait_for_selector, timeout=post_click_wait * 1000)
            except Exception:
                print("[WARN] wait_for_selector did not appear in time.")

        # Now click 'Consulta de CFE recibidos'
        print("[INFO] Clicking 'Consulta de CFE recibidos' ...")
        try:
            with final_page.expect_navigation(timeout=30000):
                final_page.click('text="Consulta de CFE recibidos"')
            final_url = final_page.url
            print("[INFO] Landed on Consulta de CFE recibidos:", final_url)
        except Exception:
            # try frames fallback
            try:
                for f in final_page.frames:
                    try:
                        if f.query_selector('text="Consulta de CFE recibidos"'):
                            f.click('text="Consulta de CFE recibidos"')
                            time.sleep(2)
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        time.sleep(post_click_wait)
        return final_page, final_url

    except Error as e:
        print("[ERROR] Playwright Error:", e)
        traceback.print_exc()
        _dump_debug(page)
        raise
    except Exception as e:
        print("[ERROR] Exception:", e)
        traceback.print_exc()
        _dump_debug(page)
        raise

# ---------------------------
# Fill filters / Consult
# ---------------------------
# (UNCHANGED)

def _click_maybe_in_frames(page, selector, timeout=2000):
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
    deadline = time.time() + (timeout / 1000)
    while time.time() < deadline:
        try:
            el = page.query_selector(selector)
            if el:
                return page, el
        except Exception:
            pass
        try:
            for frame in page.frames:
                try:
                    el = frame.query_selector(selector)
                    if el:
                        return frame, el
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.2)
    return None, None


def _set_select_value(frame_or_page, element_handle, value):
    try:
        frame_or_page.select_option(sel.SELECT_TIPO_CFE, value)
        return True
    except Exception:
        pass
    try:
        element_handle.evaluate(
            """(el, val) => {
                el.value = val;
                el.dispatchEvent(new Event('input',{bubbles:true}));
                el.dispatchEvent(new Event('change',{bubbles:true}));
                el.dispatchEvent(new Event('blur',{bubbles:true}));
                try{ if(window.gx && gx.evt && typeof gx.evt.onchange === 'function') gx.evt.onchange(el);}catch(e){}
                return true;
            }""",
            value
        )
        return True
    except Exception:
        pass
    try:
        element_handle.click()
        frame_or_page.click(f'{sel.SELECT_TIPO_CFE} >> option[value="{value}"]', timeout=2000)
        return True
    except Exception:
        pass
    return False


def _set_input_value_with_fallback(frame_or_page, element_handle, value):
    try:
        element_handle.evaluate(
            """(el, val) => {
                try{ el.focus && el.focus(); }catch(e){}
                el.value = val;
                el.dispatchEvent(new Event('input',{bubbles:true}));
                el.dispatchEvent(new Event('change',{bubbles:true}));
                el.dispatchEvent(new Event('blur',{bubbles:true}));
                try{ if(window.gx && gx.evt && typeof gx.evt.onchange === 'function') gx.evt.onchange(el); }catch(e){}
                try{ if(window.gx && gx.date && typeof gx.date.valid_date === 'function') { try{ gx.date.valid_date(el,10,'DMY',0,24,'spa',false,0);}catch(e){} } }catch(e){}
                return true;
            }""",
            value
        )
        return True
    except Exception:
        pass

    try:
        element_handle.click(timeout=2000)
        time.sleep(0.1)
        for ch in value:
            element_handle.type(ch, delay=60)
        try:
            element_handle.evaluate("(el) => { el.dispatchEvent(new Event('blur',{bubbles:true})); }")
        except Exception:
            pass
        return True
    except Exception:
        pass
    return False


def fill_cfe_and_consult(
    page,
    tipo_value: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    wait_after_result: int = 3
) -> Tuple[object, str]:
    """
    Set filters on the Consulta page and click Consultar. Returns (page, url).
    """
    try:
        tipo = tipo_value or getattr(config, "ECF_TIPO", "111")
        d_from = date_from or getattr(config, "ECF_FROM_DATE", "")
        d_to = date_to or getattr(config, "ECF_TO_DATE", "")

        print(f"[INFO] fill_cfe_and_consult: tipo={tipo}, desde={d_from}, hasta={d_to}")

        frame, el = _find_element_in_page_and_frames(page, sel.SELECT_TIPO_CFE, timeout=5000)
        if el:
            if not _set_select_value(frame, el, tipo):
                print("[WARN] Could not set tipo select by any method.")
        else:
            print("[WARN] SELECT_TIPO_CFE not found.")

        if d_from:
            f_from, el_from = _find_element_in_page_and_frames(page, sel.DATE_FROM, timeout=5000)
            if el_from:
                _set_input_value_with_fallback(f_from, el_from, d_from)
            else:
                print("[WARN] DATE_FROM not found.")

        if d_to:
            f_to, el_to = _find_element_in_page_and_frames(page, sel.DATE_TO, timeout=5000)
            if el_to:
                _set_input_value_with_fallback(f_to, el_to, d_to)
            else:
                print("[WARN] DATE_TO not found.")

        time.sleep(0.5)

        print("[INFO] Clicking Consultar...")
        try:
            with page.expect_navigation(timeout=30000):
                clicked = _click_maybe_in_frames(page, sel.BUTTON_CONSULTAR)
                if not clicked:
                    raise Exception("Could not click Consultar")
            final_url = page.url
            final_page = page
        except Exception:
            # maybe new tab
            try:
                with page.context.expect_page(timeout=5000) as ctx:
                    clicked = _click_maybe_in_frames(page, sel.BUTTON_CONSULTAR)
                    if not clicked:
                        raise Exception("Could not click Consultar (new tab attempt failed)")
                new_page = ctx.value
                try:
                    new_page.wait_for_load_state("load", timeout=30000)
                except Exception:
                    pass
                final_page = new_page
                final_url = new_page.url
            except Exception:
                # fallback click then wait
                clicked_any = _click_maybe_in_frames(page, sel.BUTTON_CONSULTAR)
                if not clicked_any:
                    _dump_debug(page)
                    return page, page.url
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    pass
                final_page = page
                final_url = page.url

        if wait_after_result and wait_after_result > 0:
            time.sleep(wait_after_result)

        return final_page, final_url

    except Exception as e:
        print("[ERROR] Exception in fill_cfe_and_consult:", e)
        traceback.print_exc()
        _dump_debug(page)
        raise

# ---------------------------
# Grid scanning / extraction
# ---------------------------
# _try_get_text and _extract_fields_from_page unchanged

def _try_get_text(element):
    if element is None:
        return ""
    try:
        tag = element.evaluate("el => el.tagName && el.tagName.toLowerCase()")
    except Exception:
        tag = None
    try:
        if tag in ("input", "textarea"):
            return element.evaluate("el => el.value ? el.value.trim() : ''") or ""
        else:
            return element.inner_text().strip()
    except Exception:
        try:
            return element.evaluate("el => el.textContent ? el.textContent.trim() : ''") or ""
        except Exception:
            return ""


def _extract_fields_from_page(p):
    mapping = {
        "Razón Social": ["#span_vDENOMINACION", '[id*="span_vDENOMINACION"]', '.ReadonlyAttribute#span_vDENOMINACION'],
        "RUT": ["#span_CTLEFACARCHEMISORDOCNRO", '[id*="CTLEFACARCHEMISORDOCNRO"]'],
        "Tipo CFE": ["#span_CTLEFACCMPTIPODESCORTA", '[id*="CTLEFACCMPTIPODESCORTA"]'],
        "Serie": ["#span_CTLEFACCFESERIE1", '[id*="CTLEFACCFESERIE1"]'],
        "Número": ["#span_CTLEFACCFENUMERO1", '[id*="CTLEFACCFENUMERO1"]'],
        "Fecha de Emisión": ["#CTLEFACCFEFIRMAFECHAHORA_dp_container", '[id*="CTLEFACCFEFIRMAFECHAHORA"]', '[id*="FECHAHORA"]'],
        "Moneda": ["#span_CTLEFACCFETIPOMONEDA", '[id*="CTLEFACCFETIPOMONEDA"]'],
        "TC": ["#span_CTLEFACCFETIPOCAMBIO", '[id*="CTLEFACCFETIPOCAMBIO"]', '[id*="TIPOCAMBIO"]'],
        "Monto No Gravado": ["#span_CTLEFACCFETOTALMONTONOGRV", '[id*="TOTALMONTONOGRV"]'],
        "Monto Exportacion y Asimilados": ["#span_CTLEFACCFETOTALMONTONOGRV", '[id*="TOTALMONTONOGRV"]'],
        "Monto Impuesto Percibido": ["#span_CTLEFACCFETOTALMNTIMPPER", '[id*="TOTALMNTIMPPER"]'],
        "Monto  IVA en suspenso": ["#span_CTLEFACCFETOTALMNTIVASUSP", '[id*="TOTALMNTIVASUSP"]'],
        "Neto Iva Tasa Básica": ["#span_CTLEFACCFETOTALMNTNETOIVATTB", '[id*="TOTALMNTNETOIVATTB"]'],
        "Neto Iva Tasa Minima": ["#span_CTLEFACCFETOTALMNTNETOIVATTM", '[id*="TOTALMNTNETOIVATTM"]'],
        "Neto Iva Otra Tasa": ["#span_CTLEFACCFETOTALMNTNETOIVATTO", '[id*="TOTALMNTNETOIVATTO"]'],
        "Monto Total": ["#span_CTLEFACCFETOTALMONTOTOTAL", '[id*="TOTALMONTOTOTAL"]'],
        "Monto Retenido": ['#TEXTBLOCK64', '[id*="TEXTBLOCK64"]', '.TextView#TEXTBLOCK64'],
        "Monto Credito Fiscal": ["#span_CTLEFACCFETOTALMONTCREDFISC", '[id*="TOTALMONTCREDFISC"]'],
        "Monto No facturable": ["#span_CTLEFACCFEMONTONOFACT", '[id*="MONTONOFACT"]'],
        "Monto Total a Pagar": ["#span_CTLEFACCFETOTALMNTAPAGAR", '[id*="TOTALMNTAPAGAR"]'],
        "Iva Tasa Básica": ["#span_CTLEFACCFETOTALIVATASABASICA", '[id*="TOTALIVATASABASICA"]'],
        "Iva Tasa Minima": ["#span_CTLEFACCFETOTALIVATASAMIN", '[id*="TOTALIVATASAMIN"]'],
        "Iva Otra Tasa": ['#span_CTLEFACCFETOTALIVAOTRATASA', '[id*="TOTALIVAOTRATASA"]'],
    }

    result = {}
    for col, selectors in mapping.items():
        found_text = ""
        for s in selectors:
            try:
                el = p.query_selector(s)
            except Exception:
                el = None
            if el:
                found_text = _try_get_text(el)
                if found_text:
                    break
        result[col] = found_text
    return result


def _collect_candidate_urls(page, parent_selector=None, link_selector=None) -> List[str]:
    """
    Scan the page and all frames and return a list of candidate URLs found in href attributes
    or inside onclick attributes. Makes relative URLs absolute.
    """
    urls = []
    frames_to_search = [page] + list(page.frames)
    tried = set()

    for p in frames_to_search:
        base = getattr(p, 'url', '') or getattr(page, 'url', '') or ''
        # if user provided a selector, use it
        selectors = [link_selector] if link_selector else [
            f"{parent_selector} a[href]" if parent_selector else "a[href]",
            f"{parent_selector} img[src]" if parent_selector else "img[src]",
            "a[onclick]",
        ]
        for selq in selectors:
            try:
                els = p.query_selector_all(selq)
            except Exception:
                els = []
            for el in els:
                try:
                    href = el.get_attribute('href')
                except Exception:
                    href = None
                try:
                    src = el.get_attribute('src')
                except Exception:
                    src = None
                try:
                    onclick = el.get_attribute('onclick')
                except Exception:
                    onclick = None

                candidate = href or src or ''
                if candidate and not candidate.lower().startswith('javascript') and candidate.strip() != '#':
                    # make absolute
                    try:
                        absurl = urllib.parse.urljoin(base, candidate)
                    except Exception:
                        absurl = candidate
                    if absurl not in tried:
                        tried.add(absurl)
                        urls.append(absurl)
                        continue

                # fallback: try to extract URL from onclick text
                if onclick:
                    # look for quoted http(s) URL inside onclick
                    m = re.search(r"['\"](https?://[^'\"]+)['\"]", onclick)
                    if m:
                        absurl = m.group(1)
                        if absurl not in tried:
                            tried.add(absurl)
                            urls.append(absurl)
                            continue
                    # sometimes onclick calls open('/path', ...)
                    m2 = re.search(r"open\(['\"]([^'\"]+)['\"]", onclick)
                    if m2:
                        try:
                            absurl = urllib.parse.urljoin(base, m2.group(1))
                        except Exception:
                            absurl = m2.group(1)
                        if absurl not in tried:
                            tried.add(absurl)
                            urls.append(absurl)
                            continue
    return urls


def _gather_candidate_link_elements(page, parent_selector=None, link_selector=None):
    """
    Legacy fallback: returns list of (frame_or_page, element_handle) that appear to be links/buttons/images for each row.
    Kept for backward compatibility but the main collector uses URLs from _collect_candidate_urls.
    """
    candidates = []
    frames_to_search = [page] + list(page.frames)
    tried = set()

    if link_selector:
        for p in frames_to_search:
            try:
                els = p.query_selector_all(link_selector)
            except Exception:
                els = []
            for el in els:
                try:
                    sig = el.evaluate("el => el.outerHTML.substring(0,200)")
                except Exception:
                    sig = str(el)
                if (getattr(p, "url", None), sig) in tried:
                    continue
                tried.add((getattr(p, "url", None), sig))
                candidates.append((p, el))
        return candidates

    parent_candidates = []
    if parent_selector:
        parent_candidates.append(parent_selector)
    parent_candidates.extend([
        "div[id*='Container']", "div[id*='sector']", "table[class*='gx-region']", "div.gx-region", "div.gxp-page", "div[id^='W']"
    ])

    for p in frames_to_search:
        for pc in parent_candidates:
            try:
                parent = p.query_selector(pc)
            except Exception:
                parent = None
            if parent:
                try:
                    elems = parent.query_selector_all("a, button, img")
                except Exception:
                    elems = []
                for el in elems:
                    try:
                        sig = el.evaluate("el => el.outerHTML.substring(0,200)")
                    except Exception:
                        sig = str(el)
                    if (getattr(p, "url", None), sig) in tried:
                        continue
                    tried.add((getattr(p, "url", None), sig))
                    try:
                        href = el.get_attribute("href")
                        onclick = el.get_attribute("onclick")
                    except Exception:
                        href = onclick = None
                    try:
                        has_img = el.evaluate("el => !!el.querySelector('img')")
                    except Exception:
                        has_img = False
                    if href or onclick or has_img:
                        candidates.append((p, el))
                if candidates:
                    return candidates

    for p in frames_to_search:
        try:
            elems = p.query_selector_all("a[href], a:has(img), img[id^='vCOLDISPLAY'], button")
        except Exception:
            elems = []
        for el in elems:
            try:
                sig = el.evaluate("el => el.outerHTML.substring(0,200)")
            except Exception:
                sig = str(el)
            if (getattr(p, "url", None), sig) in tried:
                continue
            tried.add((getattr(p, "url", None), sig))
            candidates.append((p, el))
    return candidates


def collect_cfe_from_links(page, link_selector: Optional[str] = None, output_file: str = "results.xlsx", parent_selector: Optional[str]=None) -> str:
    """
    Main function used by main.py: find document links in the grid (or using link_selector),
    open each (by URL when possible), extract fields and save incrementally to CSV.
    Returns output_file path on success (Excel if able to write, otherwise CSV).
    """
    print("[INFO] Scanning page for link elements (collecting URLs first)...")
    urls = _collect_candidate_urls(page, parent_selector=parent_selector, link_selector=link_selector)
    print(f"[INFO] Collected {len(urls)} candidate URLs.")

    # As fallback keep element handles if URLs couldn't be extracted for some entries
    fallback_elements = _gather_candidate_link_elements(page, parent_selector=parent_selector, link_selector=link_selector)
    print(f"[INFO] Found {len(fallback_elements)} candidate elements (fallback).")

    out_dir = os.path.dirname(output_file) or "."
    base_name = os.path.splitext(os.path.basename(output_file))[0]
    csv_path = os.path.join(out_dir, f"{base_name}.csv")

    # load processed URLs from existing outputs (Excel or CSV)
    processed = set()
    if os.path.exists(output_file):
        try:
            existing_df = pd.read_excel(output_file)
            if "_source_url" in existing_df.columns:
                for u in existing_df["_source_url"].fillna("").astype(str):
                    processed.add(_canonicalize_url(u))
            print(f"[INFO] Loaded {len(existing_df)} existing rows from {output_file}.")
        except Exception as e:
            print("[WARN] Could not read existing Excel (will try CSV).", e)

    if os.path.exists(csv_path):
        try:
            existing_csv = pd.read_csv(csv_path)
            if "_source_url" in existing_csv.columns:
                for u in existing_csv["_source_url"].fillna("").astype(str):
                    processed.add(_canonicalize_url(u))
            print(f"[INFO] Loaded {len(existing_csv)} existing rows from {csv_path}.")
        except Exception as e:
            print("[WARN] Could not read existing CSV.", e)

    cols_order = [
        "Razón Social", "RUT", "Tipo CFE", "Serie", "Número", "Fecha de Emisión",
        "Moneda", "TC", "Monto No Gravado", "Monto Exportacion y Asimilados",
        "Monto Impuesto Percibido", "Monto  IVA en suspenso", "Neto Iva Tasa Básica",
        "Neto Iva Tasa Minima", "Neto Iva Otra Tasa", "Monto Total", "Monto Retenido",
        "Monto Credito Fiscal", "Monto No facturable", "Monto Total a Pagar",
        "Iva Tasa Básica", "Iva Tasa Minima", "Iva Otra Tasa", "_source_url"
    ]

    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    rows_added = 0

    # First: iterate over URLs (preferred)
    for idx, url in enumerate(urls, start=1):
        canon = _canonicalize_url(url)
        if canon in processed:
            print(f"[INFO] URL already processed; skipping: {url}")
            continue
        print(f"[INFO] Opening URL {idx}/{len(urls)}: {url}")
        try:
            new_page = page.context.new_page()
            try:
                new_page.goto(url, timeout=30000)
                new_page.wait_for_load_state("load", timeout=20000)
            except Exception:
                try:
                    new_page.wait_for_load_state("networkidle", timeout=20000)
                except Exception:
                    pass

            extraction_target = new_page
            try:
                for f in getattr(new_page, 'frames', []):
                    if f.query_selector('#span_vDENOMINACION') or f.query_selector('[id*="CTLEFACCFETOTALMONTOTOTAL"]'):
                        extraction_target = f
                        break
            except Exception:
                pass

            data = _extract_fields_from_page(extraction_target)
            data['_source_url'] = url

            # append to CSV
            for c in cols_order:
                if c not in data:
                    data[c] = ''
            try:
                _append_row_to_csv(csv_path, data, fieldnames=cols_order)
                processed.add(canon)
                rows_added += 1
                print(f"[INFO] Appended row {rows_added} for {url}")
            except Exception as e:
                print("[ERROR] Could not append row:", e)

            try:
                new_page.close()
            except Exception:
                pass
        except Exception as e:
            print("[ERROR] Error opening URL:", url, e)
            try:
                new_page.close()
            except Exception:
                pass
            continue

    # Second: handle any fallback elements (those without hrefs) by clicking them one-by-one
    for idx, (frame, element) in enumerate(fallback_elements, start=1):
        # try to compute a stable identifier
        try:
            sig = element.evaluate("el => el.outerHTML.substring(0,200)")
        except Exception:
            sig = str(element)
        # Re-check if this signature already processed by comparing to processed URLs
        print(f"[INFO] Processing fallback element {idx}/{len(fallback_elements)}")
        is_new_tab = False
        final_page = page
        try:
            with page.context.expect_page(timeout=8000) as new_page_ctx:
                try:
                    element.click(timeout=5000)
                except Exception:
                    try:
                        element.evaluate("el => el.click()")
                    except Exception as e:
                        print("[ERROR] Could not click fallback element:", e)
                        continue
            new_page = new_page_ctx.value
            try:
                new_page.wait_for_load_state("load", timeout=15000)
            except Exception:
                try:
                    new_page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
            final_page = new_page
            is_new_tab = True
            print(f"[INFO] Opened new tab for fallback element: {getattr(final_page,'url','<unknown>')}")
        except TimeoutError:
            try:
                element.click(timeout=5000)
            except Exception:
                try:
                    element.evaluate("el => el.click()")
                except Exception as e:
                    print("[WARN] fallback click failed (same page):", e)
            try:
                if hasattr(frame, 'wait_for_load_state'):
                    frame.wait_for_load_state('load', timeout=8000)
                page.wait_for_load_state('load', timeout=8000)
            except Exception:
                try:
                    page.wait_for_load_state('networkidle', timeout=8000)
                except Exception:
                    pass
            final_page = page
            print('[INFO] Click triggered same-page change for fallback element.')

        try:
            extraction_target = final_page
            try:
                for f in getattr(final_page, 'frames', []):
                    if f.query_selector('#span_vDENOMINACION') or f.query_selector('[id*="CTLEFACCFETOTALMONTOTOTAL"]'):
                        extraction_target = f
                        break
            except Exception:
                pass

            data = _extract_fields_from_page(extraction_target)
            try:
                data['_source_url'] = final_page.url
            except Exception:
                data['_source_url'] = ''

            canon_url = _canonicalize_url(data.get('_source_url',''))
            if canon_url and canon_url in processed:
                print('[INFO] Fallback target already processed; skipping:', data.get('_source_url'))
            else:
                for c in cols_order:
                    if c not in data:
                        data[c] = ''
                _append_row_to_csv(csv_path, data, fieldnames=cols_order)
                if canon_url:
                    processed.add(canon_url)
                rows_added += 1
                print(f"[INFO] Appended fallback row {rows_added}")
        except Exception as e:
            print('[ERROR] Extraction for fallback element failed:', e)

        # cleanup
        try:
            if is_new_tab and final_page is not None:
                try:
                    final_page.close()
                except Exception:
                    pass
                try:
                    page.wait_for_load_state('load', timeout=2000)
                except Exception:
                    pass
            else:
                try:
                    page.go_back()
                    page.wait_for_load_state('load', timeout=5000)
                except Exception:
                    try:
                        page.reload()
                        page.wait_for_load_state('load', timeout=5000)
                    except Exception:
                        pass
        except Exception:
            pass

    # Try to write final Excel from CSV
    try:
        final_df = pd.read_csv(csv_path)
        try:
            final_df.to_excel(output_file, index=False)
            print(f"[SUCCESS] Saved {len(final_df)} rows to {output_file}")
            return output_file
        except PermissionError as pe:
            ts_path = os.path.join(out_dir, f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            try:
                final_df.to_excel(ts_path, index=False)
                print(f"[WARN] Could not overwrite {output_file} (Permission denied). Saved Excel to {ts_path} instead.")
                return ts_path
            except Exception as e:
                print("[ERROR] Could not save Excel fallback:", e)
                print("[INFO] Leaving incremental CSV at:", csv_path)
                return csv_path
    except Exception as e:
        print("[ERROR] Could not convert CSV to Excel / read CSV:", e)
        print("[INFO] Leaving incremental CSV at:", csv_path)
        return csv_path
