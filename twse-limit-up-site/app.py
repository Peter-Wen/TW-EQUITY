from __future__ import annotations

import datetime as dt
import html
import json
import math
import re
import time
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urlparse

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import requests


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CACHE_FILE = DATA_DIR / "limit_up_report.json"

TWSE_QUOTES_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
TPEX_QUOTES_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes"
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEX_INST_URL = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade"
TWSE_MARGIN_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
TPEX_MARGIN_URL = "https://www.tpex.org.tw/www/zh-tw/margin/balance"
USER_AGENT = "Mozilla/5.0 twse-limit-up-site/2.0"


def clean_text(value: Any) -> str:
    text = html.unescape("" if value is None else str(value))
    return re.sub(r"<[^>]+>", "", text).strip()


def parse_number(value: Any) -> Optional[float]:
    text = clean_text(value).replace(",", "").replace("--", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int:
    value = parse_number(value)
    return int(value) if value is not None else 0


def request_json(url: str, params: Dict[str, str], retries: int = 3) -> Dict[str, Any]:
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=25)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"無法取得官方資料：{url}") from last_error


def ymd(day: dt.date) -> str:
    return day.strftime("%Y%m%d")


def slash_date(day: dt.date) -> str:
    return day.strftime("%Y/%m/%d")


def display_date(day: str) -> str:
    return dt.datetime.strptime(day, "%Y%m%d").date().strftime("%Y-%m-%d")


def is_common_stock(code: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", code)) and int(code) >= 1000


def price_tick(price: float) -> float:
    if price < 10:
        return 0.01
    if price < 50:
        return 0.05
    if price < 100:
        return 0.1
    if price < 500:
        return 0.5
    if price < 1000:
        return 1.0
    return 5.0


def floor_to_tick(price: float) -> float:
    tick = price_tick(price)
    return round(math.floor((price + 1e-9) / tick) * tick, 2)


def limit_up_price(previous_close: float) -> float:
    return floor_to_tick(previous_close * 1.1)


def find_twse_quote_table(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for table in payload.get("tables", []):
        fields = table.get("fields") or []
        if "證券代號" in fields and "收盤價" in fields and "成交股數" in fields:
            return table
    return None


def fetch_twse_quotes(day: dt.date) -> List[Dict[str, Any]]:
    payload = request_json(TWSE_QUOTES_URL, {"date": ymd(day), "type": "ALLBUT0999", "response": "json"})
    table = find_twse_quote_table(payload)
    if not table:
        return []

    fields = table["fields"]
    rows = []
    for raw in table.get("data", []):
        record = dict(zip(fields, raw))
        code = clean_text(record.get("證券代號"))
        close = parse_number(record.get("收盤價"))
        volume = parse_int(record.get("成交股數"))
        amount = parse_int(record.get("成交金額"))
        if not is_common_stock(code) or close is None:
            continue
        rows.append(
            {
                "market": "上市",
                "key": f"TWSE:{code}",
                "code": code,
                "name": clean_text(record.get("證券名稱")),
                "volume": volume,
                "amount": amount,
                "average": round(amount / volume, 2) if volume else None,
                "open": parse_number(record.get("開盤價")),
                "high": parse_number(record.get("最高價")),
                "low": parse_number(record.get("最低價")),
                "close": close,
            }
        )
    return rows


def fetch_tpex_quotes(day: dt.date) -> List[Dict[str, Any]]:
    payload = request_json(TPEX_QUOTES_URL, {"date": slash_date(day), "response": "json"})
    tables = payload.get("tables") or []
    if not tables:
        return []

    fields = tables[0].get("fields") or []
    rows = []
    for raw in tables[0].get("data", []):
        record = dict(zip(fields, raw))
        code = clean_text(record.get("代號"))
        close = parse_number(record.get("收盤"))
        if not is_common_stock(code) or close is None:
            continue
        rows.append(
            {
                "market": "上櫃",
                "key": f"TPEX:{code}",
                "code": code,
                "name": clean_text(record.get("名稱")),
                "volume": parse_int(record.get("成交股數")),
                "amount": parse_int(record.get("成交金額(元)")),
                "average": parse_number(record.get("均價")),
                "open": parse_number(record.get("開盤")),
                "high": parse_number(record.get("最高")),
                "low": parse_number(record.get("最低")),
                "close": close,
                "next_limit_up": parse_number(record.get("次日 漲停價")),
            }
        )
    return rows


def fetch_quotes(day: dt.date) -> List[Dict[str, Any]]:
    twse_rows = fetch_twse_quotes(day)
    time.sleep(0.1)
    tpex_rows = fetch_tpex_quotes(day)
    if not twse_rows or not tpex_rows:
        return []
    return twse_rows + tpex_rows


def fetch_twse_institutional(day: dt.date) -> Dict[str, Dict[str, int]]:
    payload = request_json(TWSE_INST_URL, {"date": ymd(day), "selectType": "ALLBUT0999", "response": "json"})
    fields = payload.get("fields") or []
    result = {}
    for raw in payload.get("data", []):
        record = dict(zip(fields, raw))
        code = clean_text(record.get("證券代號"))
        if not is_common_stock(code):
            continue
        foreign_net = parse_int(record.get("外陸資買賣超股數(不含外資自營商)")) + parse_int(record.get("外資自營商買賣超股數"))
        result[f"TWSE:{code}"] = {
            "foreign_net": foreign_net,
            "investment_trust_net": parse_int(record.get("投信買賣超股數")),
            "dealer_net": parse_int(record.get("自營商買賣超股數")),
            "institutional_net": parse_int(record.get("三大法人買賣超股數")),
        }
    return result


def fetch_tpex_institutional(day: dt.date) -> Dict[str, Dict[str, int]]:
    payload = request_json(TPEX_INST_URL, {"date": slash_date(day), "type": "Daily", "response": "json"})
    tables = payload.get("tables") or []
    result = {}
    if not tables:
        return result
    for raw in tables[0].get("data", []):
        code = clean_text(raw[0]) if raw else ""
        if not is_common_stock(code) or len(raw) < 24:
            continue
        result[f"TPEX:{code}"] = {
            "foreign_net": parse_int(raw[10]),
            "investment_trust_net": parse_int(raw[13]),
            "dealer_net": parse_int(raw[22]),
            "institutional_net": parse_int(raw[23]),
        }
    return result


def fetch_institutional(day: dt.date) -> Dict[str, Dict[str, int]]:
    result: Dict[str, Dict[str, int]] = {}
    try:
        result.update(fetch_twse_institutional(day))
    except Exception:
        pass
    time.sleep(0.1)
    try:
        result.update(fetch_tpex_institutional(day))
    except Exception:
        pass
    return result


def fetch_twse_margin(day: dt.date) -> Dict[str, Dict[str, Optional[float]]]:
    payload = request_json(TWSE_MARGIN_URL, {"date": ymd(day), "selectType": "ALL", "response": "json"})
    tables = payload.get("tables") or []
    result: Dict[str, Dict[str, Optional[float]]] = {}
    margin_table = None
    for table in tables:
        fields = table.get("fields") or []
        if "代號" in fields and "次一營業日限額" in fields:
            margin_table = table
            break
    if not margin_table:
        return result
    fields = margin_table.get("fields") or []
    for raw in margin_table.get("data", []):
        record = dict(zip(fields, raw))
        code = clean_text(record.get("代號"))
        if not is_common_stock(code):
            continue
        balance = parse_number(record.get("今日餘額")) or 0
        limit = parse_number(record.get("次一營業日限額")) or 0
        usage = round((balance / limit) * 100, 2) if limit else None
        result[f"TWSE:{code}"] = {"margin_usage_rate": usage}
    return result


def fetch_tpex_margin(day: dt.date) -> Dict[str, Dict[str, Optional[float]]]:
    payload = request_json(TPEX_MARGIN_URL, {"date": slash_date(day), "response": "json"})
    tables = payload.get("tables") or []
    result: Dict[str, Dict[str, Optional[float]]] = {}
    if not tables:
        return result
    fields = tables[0].get("fields") or []
    for raw in tables[0].get("data", []):
        record = dict(zip(fields, raw))
        code = clean_text(record.get("代號"))
        if not is_common_stock(code):
            continue
        result[f"TPEX:{code}"] = {"margin_usage_rate": parse_number(record.get("資使用率(%)"))}
    return result


def fetch_margin(day: dt.date) -> Dict[str, Dict[str, Optional[float]]]:
    result: Dict[str, Dict[str, Optional[float]]] = {}
    try:
        result.update(fetch_twse_margin(day))
    except Exception:
        pass
    time.sleep(0.1)
    try:
        result.update(fetch_tpex_margin(day))
    except Exception:
        pass
    return result


def quote_index(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {row["key"]: row for row in rows}


def collect_market(today: dt.date, calendar_days: int = 45, target_trading_days: int = 20) -> Dict[str, List[Dict[str, Any]]]:
    market: Dict[str, List[Dict[str, Any]]] = {}
    for offset in range(calendar_days):
        day = today - dt.timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        try:
            rows = fetch_quotes(day)
        except Exception:
            rows = []
        if rows:
            market[ymd(day)] = rows
            if len(market) >= target_trading_days:
                break
        time.sleep(0.15)
    return dict(sorted(market.items()))


def attach_limit_flags(market: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    indexed = {day: quote_index(rows) for day, rows in market.items()}
    days = sorted(indexed)
    for idx, day in enumerate(days):
        if idx == 0:
            continue
        previous = indexed[days[idx - 1]]
        for key, row in indexed[day].items():
            prev = previous.get(key)
            if not prev:
                row["is_limit_up"] = False
                continue
            target = prev.get("next_limit_up") or limit_up_price(prev["close"])
            row["limit_up_price"] = target
            row["is_limit_up"] = abs(row["close"] - target) < 0.001
    return indexed


def consecutive_limit_days(indexed: Dict[str, Dict[str, Dict[str, Any]]], days: List[str], day_index: int, key: str) -> int:
    count = 0
    for idx in range(day_index, -1, -1):
        row = indexed[days[idx]].get(key)
        if not row or not row.get("is_limit_up"):
            break
        count += 1
    return count


def performance(indexed: Dict[str, Dict[str, Dict[str, Any]]], days: List[str], day_index: int, key: str, offset: int) -> Optional[Dict[str, Any]]:
    future_index = day_index + offset
    if future_index >= len(days):
        return None
    base = indexed[days[day_index]].get(key)
    future = indexed[days[future_index]].get(key)
    if not base or not future:
        return None
    pct = ((future["close"] - base["close"]) / base["close"]) * 100
    return {"date": display_date(days[future_index]), "close": round(future["close"], 2), "change_pct": round(pct, 2)}


def round_optional(value: Optional[float]) -> Optional[float]:
    return round(value, 2) if value is not None else None


def build_report(today: Optional[dt.date] = None) -> Dict[str, Any]:
    today = today or dt.date.today()
    market = collect_market(today)
    if not market:
        raise RuntimeError("無法取得上市與上櫃行情資料，請確認網路連線後再更新。")

    indexed = attach_limit_flags(market)
    days = sorted(indexed)
    recent_days = days[-5:]

    institutional_by_day: Dict[str, Dict[str, Dict[str, int]]] = {}
    for day in recent_days:
        institutional_by_day[day] = fetch_institutional(dt.datetime.strptime(day, "%Y%m%d").date())
        for key, inst in institutional_by_day[day].items():
            if key in indexed[day]:
                indexed[day][key].update(inst)
        margin = fetch_margin(dt.datetime.strptime(day, "%Y%m%d").date())
        for key, margin_row in margin.items():
            if key in indexed[day]:
                indexed[day][key].update(margin_row)

    pages = []
    for day in recent_days:
        day_index = days.index(day)
        stocks = []
        for row in indexed[day].values():
            if not row.get("is_limit_up"):
                continue
            stocks.append(
                {
                    "market": row["market"],
                    "code": row["code"],
                    "name": row["name"],
                    "volume": row["volume"],
                    "margin_usage_rate": round_optional(row.get("margin_usage_rate")),
                    "average": round_optional(row.get("average")),
                    "open": round_optional(row.get("open")),
                    "low": round_optional(row.get("low")),
                    "close": round(row["close"], 2),
                    "limit_up_price": round(row["limit_up_price"], 2),
                    "foreign_net": row.get("foreign_net", 0),
                    "investment_trust_net": row.get("investment_trust_net", 0),
                    "dealer_net": row.get("dealer_net", 0),
                    "institutional_net": row.get("institutional_net", 0),
                    "consecutive_limit_days": consecutive_limit_days(indexed, days, day_index, row["key"]),
                    "after_1d": performance(indexed, days, day_index, row["key"], 1),
                    "after_3d": performance(indexed, days, day_index, row["key"], 3),
                    "after_1w": performance(indexed, days, day_index, row["key"], 5),
                }
            )
        stocks.sort(key=lambda item: (-item["consecutive_limit_days"], -item["volume"], item["market"], item["code"]))
        pages.append({"date": display_date(day), "count": len(stocks), "stocks": stocks})

    report = {
        "source": "TWSE 台灣證券交易所 + TPEx 櫃買中心官方公開資料",
        "source_urls": [TWSE_QUOTES_URL, TPEX_QUOTES_URL, TWSE_INST_URL, TPEX_INST_URL, TWSE_MARGIN_URL, TPEX_MARGIN_URL],
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "trading_days": [display_date(day) for day in recent_days],
        "pages": pages,
    }
    DATA_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def read_cached_report() -> Optional[Dict[str, Any]]:
    if not CACHE_FILE.exists():
        return None
    return json.loads(CACHE_FILE.read_text(encoding="utf-8"))


INDEX_HTML = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>台股漲停追蹤</title>
  <link rel="stylesheet" href="/style.css" />
</head>
<body>
  <header class="topbar">
    <div>
      <h1>上市上櫃漲停追蹤</h1>
      <p id="meta">載入中...</p>
    </div>
    <button id="refresh" type="button">更新資料</button>
  </header>

  <main>
    <nav id="tabs" class="tabs" aria-label="近五個交易日"></nav>
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2 id="page-date"></h2>
          <p id="page-count"></p>
        </div>
        <input id="filter" type="search" placeholder="搜尋代號或名稱" />
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th><button class="sort-head" data-sort="code" type="button">代號</button></th>
              <th><button class="sort-head" data-sort="market" type="button">市場</button></th>
              <th><button class="sort-head" data-sort="name" type="button">名稱</button></th>
              <th class="num"><button class="sort-head" data-sort="volume" type="button">成交量</button></th>
              <th class="num"><button class="sort-head" data-sort="margin_usage_rate" type="button">融資使用率</button></th>
              <th class="num"><button class="sort-head" data-sort="average" type="button">均價</button></th>
              <th class="num"><button class="sort-head" data-sort="open" type="button">開盤</button></th>
              <th class="num"><button class="sort-head" data-sort="low" type="button">最低</button></th>
              <th class="num"><button class="sort-head" data-sort="close" type="button">收盤</button></th>
              <th class="num"><button class="sort-head" data-sort="foreign_net" type="button">外資</button></th>
              <th class="num"><button class="sort-head" data-sort="investment_trust_net" type="button">投信</button></th>
              <th class="num"><button class="sort-head" data-sort="dealer_net" type="button">自營商</button></th>
              <th class="num"><button class="sort-head" data-sort="institutional_net" type="button">三大合計</button></th>
              <th class="num"><button class="sort-head" data-sort="consecutive_limit_days" type="button">連續漲停</button></th>
              <th class="num"><button class="sort-head" data-sort="after_1d" type="button">1天後</button></th>
              <th class="num"><button class="sort-head" data-sort="after_3d" type="button">3天後</button></th>
              <th class="num"><button class="sort-head" data-sort="after_1w" type="button">1周後</button></th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </section>
  </main>

  <script src="/app.js"></script>
</body>
</html>
"""


STYLE_CSS = """
:root {
  color-scheme: light;
  --bg: #f7f7f4;
  --ink: #1b1d1f;
  --muted: #697078;
  --line: #d9ddd6;
  --accent: #b42318;
  --accent-ink: #ffffff;
  --panel: #ffffff;
  --green: #067647;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.topbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 22px 28px;
  border-bottom: 1px solid var(--line);
  background: #fff;
}
h1, h2, p { margin: 0; }
h1 { font-size: 24px; font-weight: 760; }
#meta, #page-count { color: var(--muted); margin-top: 6px; font-size: 14px; }
button, input {
  font: inherit;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}
button {
  min-height: 40px;
  padding: 0 16px;
  color: var(--accent-ink);
  background: var(--accent);
  border-color: var(--accent);
  cursor: pointer;
}
button:disabled { opacity: .65; cursor: wait; }
main { padding: 22px 28px 32px; }
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.tab {
  min-height: 38px;
  padding: 0 14px;
  color: var(--ink);
  background: #fff;
}
.tab.active {
  color: var(--accent-ink);
  background: #2f3a45;
  border-color: #2f3a45;
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: center;
  padding: 18px;
  border-bottom: 1px solid var(--line);
}
#filter {
  width: min(300px, 45vw);
  min-height: 40px;
  padding: 0 12px;
}
.table-wrap { overflow-x: auto; }
table {
  width: 100%;
  min-width: 1580px;
  border-collapse: collapse;
}
th, td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  white-space: nowrap;
}
th {
  color: #4c535a;
  font-size: 13px;
  background: #fafaf8;
}
.sort-head {
  min-height: auto;
  padding: 0;
  border: 0;
  border-radius: 0;
  color: inherit;
  background: transparent;
  font-size: inherit;
  font-weight: 700;
}
.sort-head::after {
  content: "↕";
  display: inline-block;
  margin-left: 5px;
  color: #9aa1a8;
  font-size: 11px;
}
.sort-head.active.asc::after { content: "↑"; color: var(--accent); }
.sort-head.active.desc::after { content: "↓"; color: var(--accent); }
.num { text-align: right; }
.badge {
  display: inline-flex;
  min-width: 44px;
  height: 24px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #eef1f4;
  color: #2f3a45;
  font-size: 12px;
  font-weight: 700;
}
.gain { color: var(--accent); font-weight: 700; }
.loss { color: var(--green); font-weight: 700; }
.muted { color: var(--muted); }
.empty {
  padding: 34px;
  text-align: center;
  color: var(--muted);
}
@media (max-width: 720px) {
  .topbar, .panel-head { align-items: stretch; flex-direction: column; }
  main, .topbar { padding-left: 16px; padding-right: 16px; }
  #filter { width: 100%; }
}
"""


APP_JS = """
let report = null;
let activeIndex = 0;
let sortState = { key: "consecutive_limit_days", direction: "desc" };

const fmt = new Intl.NumberFormat("zh-TW");
const tabs = document.querySelector("#tabs");
const rows = document.querySelector("#rows");
const meta = document.querySelector("#meta");
const pageDate = document.querySelector("#page-date");
const pageCount = document.querySelector("#page-count");
const filter = document.querySelector("#filter");
const refresh = document.querySelector("#refresh");

function perfCell(perf) {
  if (!perf) return '<span class="muted">尚無資料</span>';
  const cls = perf.change_pct >= 0 ? "gain" : "loss";
  const sign = perf.change_pct > 0 ? "+" : "";
  return `<span class="${cls}">${sign}${perf.change_pct.toFixed(2)}%</span> <span title="${perf.date}">${perf.close}</span>`;
}

function priceCell(value) {
  return value == null ? "-" : Number(value).toFixed(2).replace(/\\.00$/, "");
}

function percentCell(value) {
  return value == null ? "-" : `${Number(value).toFixed(2)}%`;
}

function signedCell(value) {
  const number = Number(value || 0);
  const cls = number >= 0 ? "gain" : "loss";
  const sign = number > 0 ? "+" : "";
  return `<span class="${cls}">${sign}${fmt.format(number)}</span>`;
}

function sortValue(stock, key) {
  if (key === "after_1d" || key === "after_3d" || key === "after_1w") {
    return stock[key] ? stock[key].change_pct : Number.NEGATIVE_INFINITY;
  }
  const value = stock[key];
  return value == null ? Number.NEGATIVE_INFINITY : value;
}

function compareStocks(a, b) {
  const left = sortValue(a, sortState.key);
  const right = sortValue(b, sortState.key);
  let result = 0;
  if (typeof left === "number" && typeof right === "number") {
    result = left - right;
  } else {
    result = String(left).localeCompare(String(right), "zh-Hant");
  }
  if (result === 0) result = a.code.localeCompare(b.code);
  return sortState.direction === "asc" ? result : -result;
}

function updateSortHeaders() {
  document.querySelectorAll(".sort-head").forEach((button) => {
    const active = button.dataset.sort === sortState.key;
    button.classList.toggle("active", active);
    button.classList.toggle("asc", active && sortState.direction === "asc");
    button.classList.toggle("desc", active && sortState.direction === "desc");
  });
}

function renderTabs() {
  tabs.innerHTML = "";
  report.pages.forEach((page, index) => {
    const button = document.createElement("button");
    button.className = `tab ${index === activeIndex ? "active" : ""}`;
    button.type = "button";
    button.textContent = page.date;
    button.addEventListener("click", () => {
      activeIndex = index;
      render();
    });
    tabs.appendChild(button);
  });
}

function renderRows() {
  const page = report.pages[activeIndex];
  const keyword = filter.value.trim().toLowerCase();
  const filtered = page.stocks.filter((stock) => {
    return !keyword || stock.code.toLowerCase().includes(keyword) || stock.name.toLowerCase().includes(keyword);
  }).sort(compareStocks);
  if (!filtered.length) {
    rows.innerHTML = `<tr><td colspan="17" class="empty">沒有符合條件的漲停股票</td></tr>`;
    return;
  }
  rows.innerHTML = filtered.map((stock) => `
    <tr>
      <td><strong>${stock.code}</strong></td>
      <td><span class="badge">${stock.market}</span></td>
      <td>${stock.name}</td>
      <td class="num">${fmt.format(stock.volume)}</td>
      <td class="num">${percentCell(stock.margin_usage_rate)}</td>
      <td class="num">${priceCell(stock.average)}</td>
      <td class="num">${priceCell(stock.open)}</td>
      <td class="num">${priceCell(stock.low)}</td>
      <td class="num">${priceCell(stock.close)}</td>
      <td class="num">${signedCell(stock.foreign_net)}</td>
      <td class="num">${signedCell(stock.investment_trust_net)}</td>
      <td class="num">${signedCell(stock.dealer_net)}</td>
      <td class="num">${signedCell(stock.institutional_net)}</td>
      <td class="num">${stock.consecutive_limit_days}</td>
      <td class="num">${perfCell(stock.after_1d)}</td>
      <td class="num">${perfCell(stock.after_3d)}</td>
      <td class="num">${perfCell(stock.after_1w)}</td>
    </tr>
  `).join("");
}

function render() {
  if (!report) return;
  const page = report.pages[activeIndex];
  meta.textContent = `${report.source}，更新時間 ${report.generated_at}`;
  pageDate.textContent = page.date;
  pageCount.textContent = `共 ${page.count} 檔上市上櫃普通股漲停`;
  renderTabs();
  updateSortHeaders();
  renderRows();
}

async function loadReport(force = false) {
  refresh.disabled = true;
  refresh.textContent = force ? "更新中..." : "載入中...";
  const response = await fetch(`/api/report${force ? "?refresh=1" : ""}`);
  if (!response.ok) throw new Error(await response.text());
  report = await response.json();
  activeIndex = Math.max(0, report.pages.length - 1);
  render();
  refresh.disabled = false;
  refresh.textContent = "更新資料";
}

filter.addEventListener("input", renderRows);
document.querySelectorAll(".sort-head").forEach((button) => {
  button.addEventListener("click", () => {
    const key = button.dataset.sort;
    if (sortState.key === key) {
      sortState.direction = sortState.direction === "asc" ? "desc" : "asc";
    } else {
      sortState = { key, direction: "desc" };
    }
    updateSortHeaders();
    renderRows();
  });
});
refresh.addEventListener("click", () => loadReport(true).catch((error) => {
  refresh.disabled = false;
  refresh.textContent = "更新資料";
  alert(error.message);
}));

loadReport(false).catch((error) => {
  meta.textContent = `載入失敗：${error.message}`;
  refresh.disabled = false;
  refresh.textContent = "更新資料";
});
"""


class Handler(BaseHTTPRequestHandler):
    def send_body(self, content: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_body(INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/style.css":
            self.send_body(STYLE_CSS.encode("utf-8"), "text/css; charset=utf-8")
            return
        if parsed.path == "/app.js":
            self.send_body(APP_JS.encode("utf-8"), "text/javascript; charset=utf-8")
            return
        if parsed.path == "/api/report":
            params = parse_qs(parsed.query)
            try:
                report = build_report() if params.get("refresh") == ["1"] else read_cached_report() or build_report()
                self.send_body(json.dumps(report, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            except Exception as exc:
                self.send_body(str(exc).encode("utf-8"), "text/plain; charset=utf-8", status=500)
            return
        self.send_body(b"Not found", "text/plain; charset=utf-8", status=404)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8055), Handler)
    print("台股漲停追蹤網站：http://127.0.0.1:8055")
    server.serve_forever()


if __name__ == "__main__":
    main()
