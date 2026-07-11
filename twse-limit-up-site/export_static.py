from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import app


ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
SNAPSHOT_FILE = ROOT / "static_report.json"


def load_report(refresh: bool) -> Dict[str, Any]:
    if refresh:
        report = app.build_report()
        SNAPSHOT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    if SNAPSHOT_FILE.exists():
        return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))

    cached = app.read_cached_report()
    if cached:
        SNAPSHOT_FILE.write_text(json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8")
        return cached

    raise RuntimeError("找不到靜態報表，請先執行：python -B export_static.py --refresh")


def static_html() -> str:
    return (
        app.INDEX_HTML.replace('href="/style.css"', 'href="./style.css"')
        .replace(
            '<script src="/app.js"></script>',
            '<script>window.TW_EQUITY_STATIC = true;</script>\n  <script src="./app.js"></script>',
        )
        .replace(
            '<button id="refresh" type="button">更新資料</button>',
            '<button id="refresh" type="button">重新載入</button>',
        )
    )


def export(refresh: bool = False) -> Dict[str, Any]:
    report = load_report(refresh)
    data_dir = PUBLIC_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    (PUBLIC_DIR / "index.html").write_text(static_html(), encoding="utf-8")
    (PUBLIC_DIR / "style.css").write_text(app.STYLE_CSS, encoding="utf-8")
    (PUBLIC_DIR / "app.js").write_text(app.APP_JS, encoding="utf-8")
    (data_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Export TW-EQUITY as a static site")
    parser.add_argument("--refresh", action="store_true", help="Fetch fresh TWSE/TPEx data before export")
    args = parser.parse_args()
    report = export(refresh=args.refresh)
    print(
        json.dumps(
            {
                "generated_at": report["generated_at"],
                "trading_days": report["trading_days"],
                "publish_dir": str(PUBLIC_DIR),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
