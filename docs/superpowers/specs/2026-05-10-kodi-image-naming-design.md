# Kodi 图片命名兼容 — 设计文档

## 问题

当前搜刮图片命名仅支持 Jellyfin/Emby，Kodi 默认皮肤 Estuary 需要不同的文件名：
- 背景图：Kodi 需要 `fanart.jpg`（当前只有 `backdrop.jpg`）
- 集缩略图：Kodi 需要 `{episode}-thumb.jpg`（当前只有 `{episode}.jpg`）

## 方案

同时保存两份文件（Emby 名 + Kodi 名），内容相同。仅修改 `app/chain/media.py`。

## 组件

### `_kodi_alternative_path` 静态方法

根据主图片路径和元数据类型，返回 Kodi 替代路径：

| 条件 | 主文件 | Kodi 替代 |
|---|---|---|
| BACKDROP + TV/MOVIE | `backdrop.jpg` | `fanart.jpg` |
| THUMB + EPISODE | `{ep}.jpg` | `{ep}-thumb.jpg` |
| 其他 | — | None（无需替代） |

### 集成点

`_scrape_images_generic` — 主图片保存成功后，调用 `_kodi_alternative_path`，若返回路径则再保存一份。

## 修改清单

| 文件 | 改动 |
|---|---|
| `app/chain/media.py` | 新增 `_kodi_alternative_path` 方法；在 `_scrape_images_generic` 中调用 |
