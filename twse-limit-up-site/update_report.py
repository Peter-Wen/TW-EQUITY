from __future__ import annotations

import json
from pathlib import Path

import app


def main() -> None:
    report = app.build_report()
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    summary = {
        "generated_at": report["generated_at"],
        "trading_days": report["trading_days"],
        "counts": [page["count"] for page in report["pages"]],
    }
    (log_dir / "last_update.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
