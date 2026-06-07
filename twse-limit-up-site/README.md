# 台股漲停追蹤網站

這是一個本機 Python 網站，資料來源使用台灣證券交易所官方 `MI_INDEX` 與櫃買中心官方上櫃股票行情資料。

## 啟動

```bash
cd /Users/peterwen/Public/twse-limit-up-site
/Users/peterwen/Public/finance-python-env/bin/python app.py
```

開啟：

```text
http://127.0.0.1:8055
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
