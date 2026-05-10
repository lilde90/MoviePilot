# Kodi 图片命名兼容 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在图片刮削时额外保存 Kodi 兼容命名的文件（fanart.jpg, {ep}-thumb.jpg）

**Architecture:** 在 `_scrape_images_generic` 主图片保存后，调用新增的 `_kodi_alternative_path` 获取 Kodi 替代路径，再保存一份。

**Tech Stack:** Python Path

---

### Task 1: 实现 Kodi 图片命名兼容

**Files:**
- Modify: `app/chain/media.py`

- [ ] **Step 1: 在 `_scrape_images_generic` 方法之后添加 `_kodi_alternative_path` 静态方法**

在 `_scrape_images_generic` 方法结束后（约第967行之后），`scrape_metadata` 方法之前添加：

```python
    @staticmethod
    def _kodi_alternative_path(
        image_path: Path,
        item_type: ScrapingTarget,
        metadata_type: ScrapingMetadata,
    ) -> Optional[Path]:
        """返回 Kodi 兼容的替代文件路径，无需替代时返回 None"""
        if metadata_type == ScrapingMetadata.BACKDROP:
            if item_type in (ScrapingTarget.TV, ScrapingTarget.MOVIE):
                return image_path.parent / f"fanart{image_path.suffix}"
        if metadata_type == ScrapingMetadata.THUMB and item_type == ScrapingTarget.EPISODE:
            stem = image_path.stem
            return image_path.parent / f"{stem}-thumb{image_path.suffix}"
        return None
```

- [ ] **Step 2: 在 `_scrape_images_generic` 中主图片保存后添加 Kodi 替代保存逻辑**

找到 `_scrape_images_generic` 中的这段代码（约第960行）：

```python
                if self._should_scrape(option, bool(file_exists), overwrite):
                    self._download_and_save_image(
                        fileitem=base_item, path=image_path, url=image_url
                    )
```

替换为：

```python
                if self._should_scrape(option, bool(file_exists), overwrite):
                    self._download_and_save_image(
                        fileitem=base_item, path=image_path, url=image_url
                    )
                    # 额外保存 Kodi 兼容命名
                    kodi_path = self._kodi_alternative_path(
                        image_path, item_type, metadata_type
                    )
                    if kodi_path:
                        kodi_exists = self.storagechain.get_file_item(
                            storage=base_item.storage, path=kodi_path
                        )
                        if self._should_scrape(option, bool(kodi_exists), overwrite):
                            self._download_and_save_image(
                                fileitem=base_item, path=kodi_path, url=image_url
                            )
```

- [ ] **Step 3: 验证模块导入正常**

Run: `cd /Users/lilde90/code/MoviePilot && python -c "from app.chain.media import MediaChain; print('OK')"`
Expected: `OK`

- [ ] **Step 4: 运行已有测试确保无回归**

Run: `cd /Users/lilde90/code/MoviePilot && python -m pytest tests/test_mediascrape.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add app/chain/media.py
git commit -m "feat(media): add Kodi-compatible image naming"
```
