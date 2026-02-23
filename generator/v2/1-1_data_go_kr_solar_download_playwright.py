import argparse
import csv
import re
from pathlib import Path
from typing import Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

TARGET_URL = "https://www.data.go.kr/data/15107742/standard.do#layer_data_infomation"


def extract_uid(onclick_value: str) -> str:
    if not onclick_value:
        return ""
    match = re.search(r"uid:([a-fA-F0-9\-]+)", onclick_value)
    return match.group(1) if match else ""


def safe_close_modal(page) -> None:
    close_buttons = page.locator("a[rel='modal:close']")
    if close_buttons.count() > 0:
        close_buttons.last.click()


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 1
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def run_crawler(
    url: str,
    download_dir: Path,
    start_index: int,
    max_items: Optional[int],
    timeout_ms: int,
    headless: bool,
):
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector("#stdFileListDiv")

        links = page.locator("#stdFileListDiv a[onclick*='fn_fileDataDetail']")
        total = links.count()
        end_index = total if max_items is None else min(total, start_index + max_items)

        for idx in range(start_index, end_index):
            status = "ok"
            title = ""
            detail_onclick = ""
            download_onclick = ""
            uid = ""
            saved_file = ""

            try:
                links = page.locator("#stdFileListDiv a[onclick*='fn_fileDataDetail']")
                link = links.nth(idx)

                title = (link.get_attribute("title") or link.inner_text() or "").strip()
                detail_onclick = link.get_attribute("onclick") or ""
                uid = extract_uid(detail_onclick)
                link.click()

                download_link = page.locator(
                    "a[onclick*='fn_fileDataDown'][onclick*='csv'], "
                    "a[onclick*='fn_fileDataDown'][onclick*='CSV']"
                ).last
                download_link.wait_for(state="visible")
                download_onclick = download_link.get_attribute("onclick") or ""

                with page.expect_download() as download_info:
                    download_link.click()
                download = download_info.value

                target = unique_path(download_dir / download.suggested_filename)
                download.save_as(str(target))
                saved_file = str(target)

                close_button = page.locator(".layer-bottom a[rel='modal:close']").last
                close_button.click()
                page.wait_for_timeout(300)

            except PlaywrightTimeoutError:
                status = "timeout"
                safe_close_modal(page)
            except Exception as exc:  # noqa: BLE001
                status = f"error:{type(exc).__name__}"
                safe_close_modal(page)

            row = {
                "index": idx,
                "uid": uid,
                "title": title,
                "status": status,
                "saved_file": saved_file,
                "detail_onclick": detail_onclick,
                "download_onclick": download_onclick,
            }
            rows.append(row)
            print(f"[{idx}] {status} | {title}")

        context.close()
        browser.close()

    return rows


def write_log(log_path: Path, rows) -> None:
    if not rows:
        return
    with log_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "index",
                "uid",
                "title",
                "status",
                "saved_file",
                "detail_onclick",
                "download_onclick",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download per-region CSV files from data.go.kr modal list with Playwright."
    )
    parser.add_argument("--url", default=TARGET_URL)
    parser.add_argument("--download-dir", default="generator/v2/source/raw_csv")
    parser.add_argument("--log-path", default="generator/v2/source/raw_csv/download_log_playwright.csv")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--timeout-ms", type=int, default=20000)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    download_dir = Path(args.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    rows = run_crawler(
        url=args.url,
        download_dir=download_dir,
        start_index=args.start_index,
        max_items=args.max_items,
        timeout_ms=args.timeout_ms,
        headless=args.headless,
    )
    write_log(Path(args.log_path), rows)
    print(f"Saved log: {args.log_path}")


if __name__ == "__main__":
    main()
