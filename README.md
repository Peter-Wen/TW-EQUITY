# TW-EQUITY

台股上市上櫃漲停股與熱門股追蹤 Web App。

主要程式在 [`twse-limit-up-site/`](twse-limit-up-site/)。

## Static deployment

此 repo 已包含 Render Blueprint 設定檔：

```text
render.yaml
```

Render 使用不休眠的 Static Site：

- Root Directory: 留空
- Build Command: `pip install -r requirements.txt && python -B twse-limit-up-site/export_static.py`
- Publish Directory: `twse-limit-up-site/public`
- Start Command: 不需要

GitHub Actions 會在台灣時間週一至週五 19:30 更新官方資料並推送新快照，Render 隨後自動發布。

詳細本地啟動與雲端部署方式請看 [`twse-limit-up-site/README.md`](twse-limit-up-site/README.md)。
