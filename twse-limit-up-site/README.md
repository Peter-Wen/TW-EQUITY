# 台股行情追蹤網站

這是一個 Python Web App，資料來源使用台灣證券交易所與櫃買中心官方公開資料。

本專案不是 Dash、Flask、FastAPI、Streamlit、React/Vite。本機模式使用 Python 標準庫 `http.server.ThreadingHTTPServer` 提供 HTML/CSS/JS 與 `/api/report` JSON API；Render 雲端模式則匯出成純靜態 HTML/CSS/JS/JSON，由 CDN 提供，不需要常駐 Python server。

本機入口與靜態匯出器是：

```text
app.py
export_static.py
```

本機原本會跑在 `http://127.0.0.1:8055/`，原因是 `app.py` 啟動 HTTP server 並使用預設 port `8055`。目前已改成支援雲端部署：

- `HOST` 環境變數，預設 `0.0.0.0`
- `PORT` 環境變數，預設 `8055`

所以本地仍可用 `http://127.0.0.1:8055/` 開啟。Render Static Site 不使用 `HOST` 或 `PORT`。

## 本地端啟動

可以直接雙擊：

```text
/Users/peterwen/Public/start_tw_equity.command
```

或用 Terminal 執行：

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

- 自動抓近十個上市上櫃交易日
- 每個交易日一個頁籤
- 列出當天上市、上櫃普通股漲停股票
- 可切換到「熱門股」子頁，列出當日成交金額前 30 名，或成交量達前 10 個交易日平均量 3 倍的股票
- 熱門股顯示當日漲跌幅、入選原因、當日成交金額排名及 10 日量比；同時符合兩項條件時只列一次
- 記錄市場別、成交量、均價、開盤價、最低價、連續第幾天漲停
- 記錄融資使用率
- 記錄外資、投信、自營商、三大法人合計買賣超股數
- 「量 / 金額」可同時切換成交資訊與法人買賣超
  - 量：成交量與法人買賣超股數除以 1000，換算成張並顯示到小數點第二位
  - 金額：成交金額使用官方成交金額；法人買賣超以股數乘以當日收盤價估算，換算成億元並顯示到小數點第二位
- 「價格明細」按鈕可顯示或隱藏均價、開盤、最低，收盤價固定顯示
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

網站會讀取新的 `data/limit_up_report.json`。如果網站已經開著，重新整理瀏覽器頁面即可看到最新近十日資料。

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

雲端版採用 Render Static Site。HTML、CSS、JavaScript 與每日報表 JSON 都是靜態檔，由 CDN 直接提供，不會因閒置休眠，也不需要等待 Python server 冷啟動。

repo root 已提供：

```text
render.yaml
```

Render 可以用 Blueprint 自動讀取設定；也可以手動建立 Static Site。

### Render Blueprint

1. 到 Render Dashboard
2. 選 New -> Blueprint
3. 連接 GitHub repo `Peter-Wen/TW-EQUITY`
4. Render 會讀取 repo root 的 `render.yaml`
5. Blueprint 會建立 `tw-equity-static` Static Site
6. 部署完成後，Render 會提供新的公開網址

既有的 `tw-equity-1` 是 Python Web Service，Render 無法原地轉換服務類型。請先建立並驗證新的 Static Site，再刪除或停用舊 Web Service。

### Render 手動 Static Site 設定

服務類型：

```text
Static Site
```

Root Directory：

```text
留空
```

Build Command：

```bash
pip install -r requirements.txt && python -B twse-limit-up-site/export_static.py
```

Publish Directory：

```text
twse-limit-up-site/public
```

Start Command：

```text
不需要
```

環境變數：

```text
不需要
```

部署成功後，Render 服務頁面會顯示公開網址，例如：

```text
https://tw-equity-static.onrender.com
```

## 雲端每日資料更新

GitHub Actions 工作流程位於：

```text
.github/workflows/update-static-report.yml
```

它會在台灣時間週一至週五 19:30：

1. 從證交所與櫃買中心抓最新資料
2. 更新 `static_report.json`
3. 自動 commit 並 push 到 `main`
4. 觸發 Render Static Site 自動部署

也可以到 GitHub repo 的 Actions -> Update static market report -> Run workflow 手動更新。

如果 GitHub Actions 無法 push，請在 repo Settings -> Actions -> General -> Workflow permissions 選擇 `Read and write permissions`。

## 靜態匯出測試

使用目前已提交的資料快照：

```bash
cd /Users/peterwen/Public/twse-limit-up-site
/Users/peterwen/Public/finance-python-env/bin/python -B export_static.py
```

抓最新資料並更新快照：

```bash
/Users/peterwen/Public/finance-python-env/bin/python -B export_static.py --refresh
```

輸出目錄是 `twse-limit-up-site/public/`。

## 可能的部署問題

- Static Site 建立後網址會與舊 Web Service 不同，請使用新服務頁面顯示的網址。
- GitHub Actions 無法 push：確認 Workflow permissions 允許寫入，且 `main` branch protection 允許 GitHub Actions bot 更新。
- 官方資料來源暫時無法連線：排程會失敗但目前靜態網站仍維持上一份成功資料，不會因此無法開啟。
