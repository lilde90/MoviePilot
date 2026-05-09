# Fanart 访问频率控制 — 设计文档

## 问题

批量媒体库搜刮时，`FanartModule` 对 fanart.tv API 发起大量无间隔请求，触发 IP 封锁。

## 方案

在 `FanartModule` 内部增加异步速率限制器，控制 API 调用最小间隔，默认每秒 1 次请求，可通过配置调整。

## 组件

### FanartRateLimiter

- 位置：`app/modules/fanart/__init__.py`
- 使用 `asyncio.Lock` + `time.monotonic()` 实现
- `acquire()` — 异步方法，获取许可前自动等待至满足最小间隔
- 类级别单例，由 `FanartModule` 持有

### 速率控制逻辑

```
acquire():
    async with lock:
        now = monotonic()
        wait = min_interval - (now - last_time)
        if wait > 0: sleep(wait)
        last_time = monotonic()
```

并发安全由 `asyncio.Lock` 保证：同时到达的请求串行处理，每个至少间隔 `min_interval` 秒。

## 集成

### 异步路径 (`__async_request_fanart`)

在 HTTP 请求前直接 `await self._rate_limiter.acquire()`。

### 同步路径 (`__request_fanart`)

同步方法通过 `asyncio.run()` 桥接限流器的 `acquire()`。当检测到已有运行中的 event loop 时，使用 `run_coroutine_threadsafe` 调度到现有 loop。

## 配置

| 配置项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `FANART_RATE_LIMIT` | float | 1.0 | 每秒最大请求数 |

## 修改清单

| 文件 | 改动 |
|---|---|
| `app/core/config.py` | 新增 `FANART_RATE_LIMIT: float = 1.0` |
| `app/modules/fanart/__init__.py` | 新增 `FanartRateLimiter` 类；`FanartModule` 初始化限流器实例；在 `__request_fanart` 和 `__async_request_fanart` 中集成 |

## 影响范围

- 仅 `FanartModule` 内部变更，调用方无需改动
- 缓存逻辑不受影响（限流在缓存之后生效，缓存命中不触发 API 调用）
- 批量搜刮时请求以每秒 1 次的速率串行发出，整体耗时增加但不再被封
