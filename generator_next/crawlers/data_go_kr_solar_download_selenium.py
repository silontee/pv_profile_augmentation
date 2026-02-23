import argparse
import csv
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

TARGET_URL = "https://www.data.go.kr/data/15107742/standard.do#layer_data_infomation"


def build_driver(download_dir: Path, headless: bool) -> webdriver.Chrome:
    options = ChromeOptions()
    prefs = {
        "download.default_directory": str(download_dir.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--window-size=1440,1200")
    if headless:
        options.add_argument("--headless=new")
    return webdriver.Chrome(options=options)


def get_detail_links(driver: webdriver.Chrome):
    return driver.find_elements(By.CSS_SELECTOR, "#stdFileListDiv a[onclick*='fn_fileDataDetail']")


def safe_close_modal(driver: webdriver.Chrome) -> None:
    close_buttons = driver.find_elements(By.CSS_SELECTOR, "a[rel='modal:close']")
    if close_buttons:
        driver.execute_script("arguments[0].click();", close_buttons[-1])


def extract_uid(onclick_value: str) -> str:
    if not onclick_value:
        return ""
    match = re.search(r"uid:([a-fA-F0-9\-]+)", onclick_value)
    return match.group(1) if match else ""


def crawl_and_download(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    start_index: int,
    max_items: int | None,
    download_wait_sec: float,
):
    wait.until(EC.presence_of_element_located((By.ID, "stdFileListDiv")))

    rows = []
    links = get_detail_links(driver)
    total = len(links)
    end_index = total if max_items is None else min(total, start_index + max_items)

    for idx in range(start_index, end_index):
        status = "ok"
        title = ""
        detail_onclick = ""
        download_onclick = ""
        uid = ""

        try:
            links = get_detail_links(driver)
            if idx >= len(links):
                break

            link = links[idx]
            title = (link.get_attribute("title") or link.text or "").strip()
            detail_onclick = link.get_attribute("onclick") or ""
            uid = extract_uid(detail_onclick)

            driver.execute_script("arguments[0].click();", link)

            download_link = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.CSS_SELECTOR,
                        "a[onclick*='fn_fileDataDown'][onclick*='csv'], "
                        "a[onclick*='fn_fileDataDown'][onclick*='CSV']",
                    )
                )
            )
            download_onclick = download_link.get_attribute("onclick") or ""

            driver.execute_script("arguments[0].click();", download_link)
            time.sleep(download_wait_sec)

            close_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".layer-bottom a[rel='modal:close']"))
            )
            driver.execute_script("arguments[0].click();", close_button)
            wait.until(EC.invisibility_of_element(close_button))

        except TimeoutException:
            status = "timeout"
            safe_close_modal(driver)
        except Exception as exc:  # noqa: BLE001
            status = f"error:{type(exc).__name__}"
            safe_close_modal(driver)

        rows.append(
            {
                "index": idx,
                "uid": uid,
                "title": title,
                "status": status,
                "detail_onclick": detail_onclick,
                "download_onclick": download_onclick,
            }
        )
        print(f"[{idx}] {status} | {title}")

    return rows


def write_log(log_path: Path, rows) -> None:
    if not rows:
        return
    with log_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["index", "uid", "title", "status", "detail_onclick", "download_onclick"],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download per-region CSV files from data.go.kr modal list (15107742)."
    )
    parser.add_argument("--url", default=TARGET_URL)
    parser.add_argument("--download-dir", default="generator_next/source/raw_csv")
    parser.add_argument("--log-path", default="generator_next/source/raw_csv/download_log.csv")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--download-wait", type=float, default=2.0)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    download_dir = Path(args.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    driver = build_driver(download_dir=download_dir, headless=args.headless)
    wait = WebDriverWait(driver, args.timeout)

    try:
        driver.get(args.url)
        rows = crawl_and_download(
            driver=driver,
            wait=wait,
            start_index=args.start_index,
            max_items=args.max_items,
            download_wait_sec=args.download_wait,
        )
        write_log(Path(args.log_path), rows)
        print(f"Saved log: {args.log_path}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
