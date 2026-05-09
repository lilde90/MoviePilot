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
            self.assertGreaterEqual(t1 - t0, 0)
            self.assertGreaterEqual(t2 - t1, 0.40)  # 允许微小误差
            self.assertGreaterEqual(t2 - t0, 0.40)

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
        self.assertGreaterEqual(call_times[-1] - call_times[0], 0.80)

    def test_acquire_sync_bridge(self):
        """验证同步 acquire_sync 正常工作"""
        t0 = time.monotonic()
        self.limiter.acquire_sync()
        t1 = time.monotonic()
        self.limiter.acquire_sync()
        t2 = time.monotonic()
        self.assertGreaterEqual(t2 - t1, 0.40)

    def test_default_rate_is_1(self):
        """验证默认速率为每秒1次"""
        limiter = FanartRateLimiter()
        self.assertEqual(limiter._min_interval, 1.0)

    def test_invalid_rate_raises_error(self):
        """验证无效速率抛出 ValueError"""
        with self.assertRaises(ValueError):
            FanartRateLimiter(rate=0)
        with self.assertRaises(ValueError):
            FanartRateLimiter(rate=-1)


class TestFanartModuleRateLimiting(unittest.TestCase):
    """FanartModule 限流集成测试"""

    def setUp(self):
        # Mock settings — must be done BEFORE importing FanartModule
        self.settings_patcher = patch(
            "app.modules.fanart.settings",
            FANART_ENABLE=True,
            FANART_API_KEY="test_key",
            FANART_RATE_LIMIT=1.0,
            PROXY=None,
            CONF=MagicMock(fanart=128, meta=3600),
        )
        self.mock_settings = self.settings_patcher.start()
        self.addCleanup(self.settings_patcher.stop)

        # Mock RequestUtils
        self.request_patcher = patch("app.modules.fanart.RequestUtils")
        self.mock_request = self.request_patcher.start()
        self.addCleanup(self.request_patcher.stop)
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        self.mock_request.return_value.get_res.return_value = mock_response

        # Mock AsyncRequestUtils
        self.async_request_patcher = patch("app.modules.fanart.AsyncRequestUtils")
        self.mock_async = self.async_request_patcher.start()
        self.addCleanup(self.async_request_patcher.stop)
        self.mock_async.return_value.get_json = AsyncMock(return_value={"status": "ok"})

        from app.modules.fanart import FanartModule

        self.module = FanartModule()
        self.module.init_module()

    def test_rate_limiter_initialized(self):
        """验证 init_module 后限流器已初始化"""
        from app.modules.fanart import FanartModule
        self.assertIsNotNone(FanartModule._rate_limiter)
        self.assertEqual(FanartModule._rate_limiter._min_interval, 1.0)

    def test_request_fanart_calls_rate_limiter(self):
        """验证同步请求方法调用了限流器"""
        from app.modules.fanart import FanartModule
        from app.schemas.types import MediaType

        with patch.object(
            FanartModule._rate_limiter, "acquire_sync",
            wraps=FanartModule._rate_limiter.acquire_sync
        ) as mock_acquire:
            FanartModule._FanartModule__request_fanart(MediaType.MOVIE, "67890")
            mock_acquire.assert_called_once()

    def test_async_request_fanart_calls_rate_limiter(self):
        """验证异步请求方法调用了限流器"""
        from app.modules.fanart import FanartModule
        from app.schemas.types import MediaType

        async def run():
            with patch.object(
                FanartModule._rate_limiter, "acquire",
                wraps=FanartModule._rate_limiter.acquire
            ) as mock_acquire:
                await FanartModule._FanartModule__async_request_fanart(MediaType.MOVIE, "12345")
                mock_acquire.assert_called_once()

        asyncio.run(run())

    def test_stop_clears_rate_limiter(self):
        """验证 stop 清除限流器"""
        from app.modules.fanart import FanartModule
        self.module.stop()
        self.assertIsNone(FanartModule._rate_limiter)

    def test_request_fanart_safe_without_limiter(self):
        """验证限流器未初始化时同步请求不会崩溃"""
        from app.modules.fanart import FanartModule
        from app.schemas.types import MediaType

        # 确保限流器为 None
        FanartModule._rate_limiter = None
        try:
            FanartModule._FanartModule__request_fanart(MediaType.MOVIE, "12345")
        except AttributeError:
            self.fail("request_fanart raised AttributeError when rate_limiter is None")

    def test_async_request_fanart_safe_without_limiter(self):
        """验证限流器未初始化时异步请求不会崩溃"""
        from app.modules.fanart import FanartModule
        from app.schemas.types import MediaType

        async def run():
            FanartModule._rate_limiter = None
            try:
                await FanartModule._FanartModule__async_request_fanart(MediaType.MOVIE, "12345")
            except AttributeError:
                self.fail("async_request_fanart raised AttributeError when rate_limiter is None")

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
