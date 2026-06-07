# TW-EQUITY

台股上市上櫃漲停追蹤 Web App。

主要程式在 [`twse-limit-up-site/`](twse-limit-up-site/)。

## Deploy

此 repo 已包含 Render Blueprint 設定檔：

```text
render.yaml
```

在 Render 建立 Blueprint 或 Web Service 時，服務會使用：

- Root Directory: `twse-limit-up-site`
- Build Command: `pip install -r requirements.txt`
- Start Command: `python -B app.py`

詳細本地啟動與雲端部署方式請看 [`twse-limit-up-site/README.md`](twse-limit-up-site/README.md)。
