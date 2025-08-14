# src/main.py — runnable example with headed / devtools / pause support
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from src import auth
from src import selectors as sel
import src.config as config

def run(headed: bool = False, pause_on_end: bool = False, devtools: bool = False):
    Path(config.DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(Path(config.OUTPUT_FILE).parent).mkdir(parents=True, exist_ok=True)

    # Determine final headless value:
    headless = not headed if headed else config.HEADLESS

    print(f"[INFO] Launching browser (headless={headless}, headed={headed}, devtools={devtools})")
    with sync_playwright() as p:
        slow_mo = 50 if not headless else 0

        browser = p.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
            devtools=devtools if headed else False
        )

        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()

        login_url = getattr(config, "START_URL", "https://servicios.dgi.gub.uy/serviciosenlinea")
        print('[INFO] Navigating to', login_url)
        try:
            page.goto(login_url, wait_until='networkidle', timeout=60000)
        except Exception as e:
            print('[WARN] initial goto failed or timed out:', e)

        # Save a quick screenshot so you can check what the page looked like
        try:
            Path('debug').mkdir(parents=True, exist_ok=True)
            page.screenshot(path='debug/after_goto.png', full_page=True)
            print('[INFO] Saved debug screenshot: debug/after_goto.png')
        except Exception as e:
            print('[WARN] Could not save screenshot:', e)

        # perform login and navigate to Consulta de CFE recibidos
        try:
            final_page, final_url = auth.login_and_continue(page, post_click_wait=5, wait_for_selector=sel.SELECT_TIPO_CFE)
            print('[INFO] Reached', final_url)
        except Exception as e:
            print('[ERROR] login_and_continue failed:', e)
            browser.close()
            return

        # Optionally fill the tipo/date and click consultar
        try:
            final_page, results_url = auth.fill_cfe_and_consult(
                final_page,
                tipo_value=config.ECF_TIPO,
                date_from=config.ECF_FROM_DATE,
                date_to=config.ECF_TO_DATE,
                wait_after_result=3
            )
            print('[INFO] Results page URL:', results_url)
        except Exception as e:
            print('[WARN] fill_cfe_and_consult failed:', e)

        # Collect links from the results grid and extract fields
        try:
            link_selector = getattr(sel, "GRID_LINKS_SELECTOR", None)
            out = auth.collect_cfe_from_links(final_page, link_selector=link_selector, output_file=config.OUTPUT_FILE, parent_selector=getattr(sel, "GRID_PARENT_SELECTOR", None))
            print('[INFO] Extraction saved to:', out)
        except Exception as e:
            print('[ERROR] collect_cfe_from_links failed:', e)

        # If headed and pause requested, open Playwright inspector (page.pause) so you can interact
        if headed and pause_on_end:
            try:
                print('[INFO] Pausing page — you can inspect manually. Close the inspector or resume to continue.')
                page.pause()
            except Exception as e:
                print('[WARN] page.pause() not available or failed:', e)
                time.sleep(20)

        # keep browser open a short while so you can see final state (only useful in headed mode)
        if headed and not pause_on_end:
            print('[INFO] Sleeping 5s so you can see final page...')
            time.sleep(5)

        browser.close()
        print('[INFO] Browser closed. Done.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run CFE extraction (Playwright).')
    parser.add_argument('--headed', action='store_true', help='Run with visible browser (overrides HEADLESS env).')
    parser.add_argument('--pause', action='store_true', help='Pause at the end (Playwright inspector) so you can inspect manually. Only useful when --headed is set.')
    parser.add_argument('--devtools', action='store_true', help='Open DevTools for the browser (only applies when --headed).')

    args = parser.parse_args()
    run(headed=args.headed, pause_on_end=args.pause, devtools=args.devtools)
