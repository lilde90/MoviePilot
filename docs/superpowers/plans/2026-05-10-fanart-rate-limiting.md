# Fanart 访问频率控制 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `FanartModule` 中增加可配置的 API 速率限制（默认每秒1次），防止批量搜刮时被封 IP。

**Architecture:** 在 fanart 模块内新增 `FanartRateLimiter` 异步限流器（`asyncio.Lock` + `time.monotonic()`），同步路径通过 `asyncio.run()` 桥接。限流器在 HTTP 请求之前、缓存查询之后介入。

**Tech Stack:** Python asyncio, time.monotonic, unittest + MagicMock

---

### Task 1: 新增 `FANART_RATE_LIMIT` 配置项

**Files:**
- Modify: `app/core/config.py:222-222`

- [ ] **Step 1: 在 Fanart 配置区域添加速率限制配置**

```python
# app/core/config.py — 在 FANART_API_KEY 行之后添加

    # Fanart API Key
    FANART_API_KEY: str = "d2d31f9ecabea050fc7d68aa3146015f"
    # Fanart API 请求速率限制（次/秒），默认1次/秒
    FANART_RATE_LIMIT: float = 1.0
```

- [ ] **Step 2: 验证配置可正常加载**

Run: `cd /Users/lilde90/code/MoviePilot && python -c "from app.core.config import settings; print(settings.FANART_RATE_LIMIT)"`
Expected: `1.0`

- [ ] **Step 3: Commit**

```bash
git add app/core/config.py
git commit -m "feat(config): add FANART_RATE_LIMIT setting for fanart API rate limiting"
```

---

### Task 2: 实现 `FanartRateLimiter` 并集成到 `FanartModule`

**Files:**
- Modify: `app/modules/fanart/__init__.py`（多处改动）

- [ ] **Step 1: 在 `FanartModule` 类定义之前添加 `FanartRateLimiter` 类**

在 `import` 区域之后、`class FanartModule` 定义之前添加（约第13行之后）：

```python
class FanartRateLimiter:
    """Fanart API 异步速率限制器"""

    def __init__(self, rate: float = 1.0):
        self._min_interval = 1.0 / rate
        self._last_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """获取访问许可，必要时等待"""
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_time)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_time = time.monotonic()

    def acquire_sync(self):
        """同步桥接 — 无运行中 event loop 时用 asyncio.run()；否则用独立线程"""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.acquire())
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.acquire())
                future.result(timeout=30)
```

- [ ] **Step 2: 在 `FanartModule` 类中添加类属性 `_rate_limiter`**

在 `FanartModule` 类中（约第14行，`_ModuleBase` 之后、docstring 之前）：

```python
class FanartModule(_ModuleBase):
    # 速率限制器（类级别单例）
    _rate_limiter: FanartRateLimiter = None
    """
    {
        "name": "The Wheel of Time",
```

- [ ] **Step 3: 在 `init_module` 中初始化速率限制器**

修改 `init_module` 方法（约第319行），将 `pass` 替换为：

```python
def init_module(self) -> None:
    self.__class__._rate_limiter = FanartRateLimiter(
        rate=settings.FANART_RATE_LIMIT
    )
```

- [ ] **Step 4: 在 `__async_request_fanart` 中集成限流器（异步路径）**

修改 `__async_request_fanart` 方法（约第582行），在生成 URL 后、发出 HTTP 请求前添加 `await cls._rate_limiter.acquire()`：

```python
@classmethod
@cached(maxsize=settings.CONF.fanart, ttl=settings.CONF.meta, shared_key="get")
async def __async_request_fanart(
    cls, media_type: MediaType, queryid: Union[str, int]
) -> Optional[dict]:
    image_url = cls.__fanart_url(media_type=media_type, queryid=queryid)
    try:
        await cls._rate_limiter.acquire()
        ret = await AsyncRequestUtils(proxies=cls._proxies, timeout=10).get_json(
            image_url
        )
        if ret:
            return ret
        logger.debug(f"未能获取到 {queryid} 的Fanart图片")
        return {}
    except Exception as err:
        logger.error(f"获取{queryid}的Fanart图片失败：{str(err)}")
        return None
```

- [ ] **Step 5: 在 `__request_fanart` 中集成限流器（同步路径）**

修改 `__request_fanart` 方法（约第563行），在生成 URL 后、发出 HTTP 请求前添加 `cls._rate_limiter.acquire_sync()`：

```python
@classmethod
@cached(maxsize=settings.CONF.fanart, ttl=settings.CONF.meta, shared_key="get")
def __request_fanart(
    cls, media_type: MediaType, queryid: Union[str, int]
) -> Optional[dict]:
    image_url = cls.__fanart_url(media_type=media_type, queryid=queryid)
    try:
        cls._rate_limiter.acquire_sync()
        ret = RequestUtils(proxies=cls._proxies, timeout=10).get_res(
            image_url, raise_exception=True
        )
        if ret:
            return ret.json()
        else:
            logger.debug(f"未能获取到 {queryid} 的Fanart图片")
            return {}
    except Exception as err:
        logger.error(f"获取{queryid}的Fanart图片失败：{str(err)}")
        return None
```

- [ ] **Step 6: 在 `stop` 方法中清理限流器**

修改 `stop` 方法（约第322行），将 `pass` 替换为：

```python
def stop(self):
    self.__class__._rate_limiter = None
```

- [ ] **Step 7: 验证模块导入正常**

Run: `cd /Users/lilde90/code/MoviePilot && python -c "from app.modules.fanart import FanartModule, FanartRateLimiter; print('OK')"`
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add app/modules/fanart/__init__.py
git commit -m "feat(fanart): add rate limiter to control API request frequency"
```

---

### Task 3: 编写测试

**Files:**
- Create: `tests/test_fanart_rate_limiter.py`

- [ ] **Step 1: 创建测试文件**

```python
import asyncio
import time
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

from app.modules.fanart import FanartRateLimiter


class TestFanartRateLimiter(unittest.TestCase):
    """FanartRateLimiter 单元测试"""

    def setUp(self):
        self.limiter = FanartRateLimiter(rate=2.0)  # 每秒2次，间隔0.5秒

    def test_acquire_enforces_min_interval(self):
        """验证 acquire 强制最小间隔"""
        async def run():
            t0 = time.monotonic()
            await self.limiter.acquire()
            t1 = time.monotonic()
            await self.limiter.acquire()
            t2 = time.monotonic()
            # 两次请求间隔应 >= 0.5秒
            self.assertGreaterEqual(t1 - t0, 0)
            self.assertGreaterEqual(t2 - t1, 0.45)  # 允许微小误差
            self.assertGreaterEqual(t2 - t0, 0.45)

        asyncio.run(run())

    def test_concurrent_calls_serialized(self):
        """验证并发调用被正确串行化"""
        call_times = []

        async def worker():
            await self.limiter.acquire()
            call_times.append(time.monotonic())

        async def run():
            await asyncio.gather(worker(), worker(), worker())

        asyncio.run(run())
        # 三次调用应至少间隔 0.5*2=1.0 秒
        self.assertGreaterEqual(call_times[-1] - call_times[0], 0.9)

    def test_acquire_sync_bridge(self):
        """验证同步桥接在无 event loop 时正常工作"""
        t0 = time.monotonic()
        self.limiter.acquire_sync()
        t1 = time.monotonic()
        self.limiter.acquire_sync()
        t2 = time.monotonic()
        self.assertGreaterEqual(t2 - t1, 0.45)

    def test_default_rate_is_1(self):
        """验证默认速率为每秒1次"""
        limiter = FanartRateLimiter()
        self.assertEqual(limiter._min_interval, 1.0)


class TestFanartModuleRateLimiting(unittest.TestCase):
    """FanartModule 限流集成测试"""

    def setUp(self):
        # Mock settings
        self.settings_patcher = patch(
            "app.modules.fanart.settings",
            FANART_ENABLE=True,
            FANART_API_KEY="test_key",
            PROXY=None,
            CONF=MagicMock(fanart=128, meta=3600),
        )
        self.mock_settings = self.settings_patcher.start()
        self.addCleanup(self.settings_patcher.stop)

        # Mock RequestUtils / AsyncRequestUtils
        self.request_patcher = patch(
            "app.modules.fanart.RequestUtils"
        )
        self.mock_request = self.request_patcher.start()
        self.addCleanup(self.request_patcher.stop)
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        self.mock_request.return_value.get_res.return_value = mock_response

        self.async_request_patcher = patch(
            "app.modules.fanart.AsyncRequestUtils"
        )
        mock_async = self.async_request_patcher.start()
        self.addCleanup(self.async_request_patcher.stop)
        mock_async_get = AsyncMock(return_value={"status": "ok"})
        mock_async.return_value.get_json = mock_async_get

        from app.modules.fanart import FanartModule

        self.module = FanartModule()
        self.module.init_module()

    def test_rate_limiter_initialized(self):
        """验证 init_module 后限流器已初始化"""
        self.assertIsNotNone(FanartModule._rate_limiter)
        self.assertEqual(FanartModule._rate_limiter._min_interval, 1.0)

    def test_request_fanart_calls_rate_limiter(self):
        """验证同步请求方法调用了限流器"""
        from app.modules.fanart import FanartModule
        from app.schemas.types import MediaType

        with patch.object(
            FanartModule._rate_limiter, "acquire_sync", wraps=FanartModule._rate_limiter.acquire_sync
        ) as mock_acquire:
            FanartModule._FanartModule__request_fanart(MediaType.MOVIE, "12345")
            mock_acquire.assert_called_once()

    def test_async_request_fanart_calls_rate_limiter(self):
        """验证异步请求方法调用了限流器"""
        from app.modules.fanart import FanartModule
        from app.schemas.types import MediaType

        async def run():
            with patch.object(
                FanartModule._rate_limiter, "acquire", wraps=FanartModule._rate_limiter.acquire
            ) as mock_acquire:
                await FanartModule._FanartModule__async_request_fanart(MediaType.MOVIE, "12345")
                mock_acquire.assert_called_once()

        asyncio.run(run())

    def test_stop_clears_rate_limiter(self):
        """验证 stop 清除限流器"""
        self.module.stop()
        self.assertIsNone(FanartModule._rate_limiter)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试验证失败（限流器代码尚未集成时测试应部分失败）**

Run: `cd /Users/lilde90/code/MoviePilot && python -m pytest tests/test_fanart_rate_limiter.py -v`
Expected: `FanartRateLimiter` 相关测试 PASS，集成测试依赖 mock 配置

- [ ] **Step 3: Commit**

```bash
git add tests/test_fanart_rate_limiter.py
git commit -m "test(fanart): add rate limiter unit and integration tests"
```

---

### Task 4: 运行全部测试并验证

- [ ] **Step 1: 运行 fanart 相关测试**

Run: `cd /Users/lilde90/code/MoviePilot && python -m pytest tests/test_fanart_rate_limiter.py -v`
Expected: 全部 PASS

- [ ] **Step 2: 运行已有测试确保无回归**

Run: `cd /Users/lilde90/code/MoviePilot && python tests/run.py`
Expected: 全部 PASS

- [ ] **Step 3: 验证模块连接性**

Run: `cd /Users/lilde90/code/MoviePilot && python -c "
from app.modules.fanart import FanartModule
m = FanartModule()
m.init_module()
print('Module initialized:', m.get_name())
print('Rate limiter ready:', FanartModule._rate_limiter is not None)
"`
Expected: `Module initialized: Fanart` + `Rate limiter ready: True`
