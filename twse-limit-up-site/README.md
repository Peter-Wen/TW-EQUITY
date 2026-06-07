# 台股漲停追蹤網站

這是一個 Python Web App，資料來源使用台灣證券交易所與櫃買中心官方公開資料。

本專案不是 Dash、Flask、FastAPI、Streamlit、React/Vite；目前使用 Python 標準庫 `http.server.ThreadingHTTPServer` 提供 HTML/CSS/JS 與 `/api/report` JSON API。

入口檔案是：

```text
app.py
```

本機原本會跑在 `http://127.0.0.1:8055/`，原因是 `app.py` 啟動 HTTP server 並使用預設 port `8055`。目前已改成支援雲端部署：

- `HOST` 環境變數，預設 `0.0.0.0`
- `PORT` 環境變數，預設 `8055`

所以本地仍可用 `http://127.0.0.1:8055/` 開啟，Render 則會自動使用平台提供的 `PORT`。

## 本地端啟動

```bash
cd /Users/peterwen/Public/twse-limit-up-site
/Users/peterwen/Public/finance-python-env/bin/python app.py
```

開啟：

```text
http://127.0.0.1:8055
```

如果使用一般 Python 環境：

```bash
cd twse-limit-up-site
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -B app.py
```

## 功能

- 自動抓近五個上市上櫃交易日
- 每個交易日一個頁籤
- 列出當天上市、上櫃普通股漲停股票
- 記錄市場別、成交量、均價、開盤價、最低價、連續第幾天漲停
- 記錄融資使用率
- 記錄外資、投信、自營商、三大法人合計買賣超股數
- 點擊表格欄位標題可排序，再點一次可切換升冪/降冪
- 顯示 1 個交易日、3 個交易日、5 個交易日後的收盤表現
- 查詢結果會存到 `data/limit_up_report.json`

近幾日的未來表現若尚未有交易資料，畫面會顯示「尚無資料」。

## 手動更新資料

每天收盤後可以執行：

```bash
cd /Users/peterwen/Public/twse-limit-up-site
./run_daily_update.sh
```

網站會讀取新的 `data/limit_up_report.json`。如果網站已經開著，重新整理瀏覽器頁面即可看到最新近五日資料。

## macOS 每日自動更新

排程檔已放在：

```text
/Users/peterwen/Public/twse-limit-up-site/com.peterwen.twse-limit-up.update.plist
```

它預設每天 18:30 更新一次。啟用方式：

```bash
mkdir -p ~/Library/LaunchAgents
cp /Users/peterwen/Public/twse-limit-up-site/com.peterwen.twse-limit-up.update.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.peterwen.twse-limit-up.update.plist
```

更新紀錄會寫到：

```text
/Users/peterwen/Public/twse-limit-up-site/logs/
```

## Render 雲端部署

建議平台：Render。

原因：

- 這是長時間執行的 Python HTTP server，適合 Render Web Service。
- 不是純靜態站，因此不適合 Netlify/Vercel 靜態部署。
- 不是 Streamlit app，因此不適合 Streamlit Community Cloud。

repo root 已提供：

```text
render.yaml
```

Render 可以用 Blueprint 自動讀取設定；也可以手動建立 Web Service。

### Render Blueprint

1. 到 Render Dashboard
2. 選 New -> Blueprint
3. 連接 GitHub repo `Peter-Wen/TW-EQUITY`
4. Render 會讀取 repo root 的 `render.yaml`
5. 部署完成後，Render 會提供公開網址

### Render 手動 Web Service 設定

服務類型：

```text
Web Service
```

Runtime：

```text
Python
```

Root Directory：

```text
twse-limit-up-site
```

Build Command：

```bash
pip install -r requirements.txt
```

Start Command：

```bash
python -B app.py
```

環境變數：

```text
PORT
```

Render 會自動提供 `PORT`，通常不需要手動設定。可選環境變數：

```text
HOST=0.0.0.0
```

部署成功後，Render 服務頁面會顯示公開網址，例如：

```text
https://tw-equity.onrender.com
```

## 可能的部署問題

- 官方資料來源暫時無法連線：首頁第一次載入或按「更新資料」可能較慢，稍後重試即可。
- Render Free Plan 休眠：一段時間沒人使用後會休眠，第一次打開會比較慢。
- `PORT` 沒有正確綁定：確認 start command 是 `python -B app.py`，且程式使用 `0.0.0.0` 與環境變數 `PORT`。
