from pathlib import Path

import polars as pl


RAW_DIR = Path("src/data/raw_csv")
OUT_DIR = Path("src/data/final")
OUT_CSV = OUT_DIR / "pv_facility_profile_merged.csv"

SKIP_FILES = {"pv_facility_profile_state.csv", "download_log_playwright.csv"}


def main() -> None:
    files = sorted(
        p for p in RAW_DIR.glob("*.csv") if p.is_file() and p.name not in SKIP_FILES
    )
    if not files:
        raise SystemExit("No raw CSV files found.")

    frames: list[pl.DataFrame] = []
    for file_path in files:
        df = pl.read_csv(
            file_path,
            encoding="utf8-lossy",
            infer_schema_length=1000,
            ignore_errors=True,
        ).with_columns(pl.lit(file_path.name).alias("source_file"))
        frames.append(df)

    merged = pl.concat(frames, how="diagonal_relaxed")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    merged.write_csv(OUT_CSV, include_bom=True)

    print(f"merged_files={len(files)}")
    print(f"merged_rows={merged.height}")
    print(f"merged_cols={merged.width}")
    print(f"output={OUT_CSV}")


if __name__ == "__main__":
    main()
