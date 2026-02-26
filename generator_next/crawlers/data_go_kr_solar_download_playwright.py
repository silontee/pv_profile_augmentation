import argparse
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

TARGET_URL = "https://www.data.go.kr/data/15107742/standard.do#layer_data_infomation"


def extract_uid(onclick_value: str) -> str:
    if not onclick_value:
        return ""
    match = re.search(r"(?:uid|uddi):([a-fA-F0-9\-]+)", onclick_value)
    return match.group(1) if match else ""


def extract_page_no(onclick_value: str) -> Optional[int]:
    if not onclick_value:
        return None
    match = re.search(r"fn_pageClick\((\d+)\)", onclick_value)
    return int(match.group(1)) if match else None


def extract_modified_date(link) -> str:
    try:
        text = link.locator("xpath=ancestor::li[1]//div[contains(@class,'txt')]").inner_text().strip()
    except Exception:  # noqa: BLE001
        return ""
    match = re.search(r"수정일\s*:\s*(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else ""


def safe_close_modal(page) -> bool:
    close_buttons = page.locator("a[rel='modal:close']")
    try:
        count = close_buttons.count()
    except Exception:  # noqa: BLE001
        return False

    for idx in range(count - 1, -1, -1):
        button = close_buttons.nth(idx)
        try:
            button.click(timeout=1500)
            page.wait_for_timeout(150)
            return True
        except Exception:  # noqa: BLE001
            try:
                button.click(timeout=1500, force=True)
                page.wait_for_timeout(150)
                return True
            except Exception:  # noqa: BLE001
                continue
    return False


def get_max_page(page) -> int:
    candidates = page.locator("a[onclick*='fn_pageClick']")
    count = candidates.count()
    max_page = 1
    for idx in range(count):
        onclick_value = candidates.nth(idx).get_attribute("onclick") or ""
        page_no = extract_page_no(onclick_value)
        if page_no is not None:
            max_page = max(max_page, page_no)
    return max_page


def move_to_page(page, page_no: int) -> None:
    page.evaluate("target => stdObj.fn_pageClick(target)", page_no)
    page.wait_for_timeout(700)
    page.wait_for_selector("#stdFileListDiv a[onclick*='fn_fileDataDetail']")


def make_state_key(uid: str, title: str) -> str:
    if uid:
        return f"uid:{uid}"
    return f"title:{title}"


def load_state(state_path: Path) -> dict[str, dict[str, str]]:
    if not state_path.exists():
        return {}
    state: dict[str, dict[str, str]] = {}
    with state_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row.get("key", "")
            if key:
                state[key] = row
    return state


def write_state(state_path: Path, state: dict[str, dict[str, str]]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["key", "uid", "title", "modified_date", "saved_file", "updated_at", "status"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for key in sorted(state.keys()):
            writer.writerow(state[key])


def is_up_to_date(
    state: dict[str, dict[str, str]],
    key: str,
    modified_date: str,
    download_dir: Path,
) -> bool:
    entry = state.get(key)
    if not entry:
        return False
    if not modified_date or entry.get("modified_date", "") != modified_date:
        return False

    saved_file = entry.get("saved_file", "")
    if not saved_file:
        return False
    saved_path = Path(saved_file)
    if not saved_path.is_absolute():
        saved_path = (Path.cwd() / saved_path).resolve()

    download_root = download_dir.resolve()
    return saved_path.exists() and (saved_path.parent == download_root or download_root in saved_path.parents)


def run_crawler(
    url: str,
    download_dir: Path,
    state: dict[str, dict[str, str]],
    timeout_ms: int,
    headless: bool,
    max_attempts: int,
):
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector("#stdFileListDiv")

        page_no = 1
        global_index = 0

        while True:
            total_pages = get_max_page(page)
            if page_no > total_pages:
                break

            move_to_page(page, page_no)
            links = page.locator("#stdFileListDiv a[onclick*='fn_fileDataDetail']")
            link_count = links.count()
            print(f"[page {page_no}] items={link_count}")

            for idx in range(link_count):
                status = "ok"
                title = ""
                detail_onclick = ""
                download_onclick = ""
                uid = ""
                saved_file = ""
                modified_date = ""
                state_key = ""

                try:
                    links = page.locator("#stdFileListDiv a[onclick*='fn_fileDataDetail']")
                    link = links.nth(idx)

                    title = (link.get_attribute("title") or link.inner_text() or "").strip()
                    detail_onclick = link.get_attribute("onclick") or ""
                    uid = extract_uid(detail_onclick)
                    modified_date = extract_modified_date(link)
                    state_key = make_state_key(uid, title)

                    if is_up_to_date(state, state_key, modified_date, download_dir):
                        status = "skipped:up_to_date"
                    else:
                        attempt = 0
                        while attempt < max_attempts:
                            attempt += 1
                            try:
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

                                target = download_dir / download.suggested_filename
                                download.save_as(str(target))
                                saved_file = str(target)

                                if not safe_close_modal(page):
                                    status = "warn:close_failed"
                                page.wait_for_timeout(300)
                                break
                            except PlaywrightTimeoutError:
                                status = f"timeout:attempt_{attempt}"
                                safe_close_modal(page)
                                if attempt >= max_attempts:
                                    status = "timeout"
                            except Exception as exc:  # noqa: BLE001
                                status = f"error:{type(exc).__name__}:attempt_{attempt}"
                                safe_close_modal(page)
                                if attempt >= max_attempts:
                                    status = f"error:{type(exc).__name__}"

                except PlaywrightTimeoutError:
                    status = "timeout"
                    safe_close_modal(page)
                except Exception as exc:  # noqa: BLE001
                    status = f"error:{type(exc).__name__}"
                    safe_close_modal(page)

                if state_key and status in {"ok", "warn:close_failed", "skipped:up_to_date"}:
                    previous_saved_file = state.get(state_key, {}).get("saved_file", "")
                    state[state_key] = {
                        "key": state_key,
                        "uid": uid,
                        "title": title,
                        "modified_date": modified_date,
                        "saved_file": saved_file or previous_saved_file,
                        "updated_at": datetime.now().isoformat(timespec="seconds"),
                        "status": status,
                    }

                row = {
                    "index": global_index,
                    "page": page_no,
                    "page_index": idx,
                    "uid": uid,
                    "title": title,
                    "modified_date": modified_date,
                    "status": status,
                    "saved_file": saved_file,
                    "detail_onclick": detail_onclick,
                    "download_onclick": download_onclick,
                }
                rows.append(row)
                print(f"[{global_index}] p{page_no}:{idx} {status} | {title} | modified={modified_date}")
                global_index += 1

            page_no += 1

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
                "page",
                "page_index",
                "uid",
                "title",
                "modified_date",
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
    parser.add_argument("--download-dir", default="generator_next/source/raw_csv")
    parser.add_argument("--log-path", default="generator_next/source/raw_csv/download_log_playwright.csv")
    parser.add_argument("--state-path", default="generator_next/source/raw_csv/pv_facility_profile_state.csv")
    parser.add_argument("--timeout-ms", type=int, default=45000)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    download_dir = Path(args.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    state_path = Path(args.state_path)
    state = load_state(state_path)

    rows = run_crawler(
        url=args.url,
        download_dir=download_dir,
        state=state,
        timeout_ms=args.timeout_ms,
        headless=args.headless,
        max_attempts=args.max_attempts,
    )
    write_log(Path(args.log_path), rows)
    write_state(state_path, state)
    print(f"Saved log: {args.log_path}")
    print(f"Saved state: {args.state_path}")


if __name__ == "__main__":
    main()
