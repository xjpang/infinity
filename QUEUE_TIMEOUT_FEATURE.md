# Queue Timeout Feature

## 概述

队列超时功能允许自动清理在队列中等待时间过长的请求,防止请求无限期等待,提高系统的响应性和可靠性。

## 功能说明

当请求在队列中等待的时间超过配置的超时时间时,该请求会被自动取消,并返回 `TimeoutError` 异常给客户端。

### 主要特性

- ✅ **可配置超时时间**: 通过环境变量 `INFINITY_QUEUE_TIMEOUT` 设置
- ✅ **自动清理**: 超时请求会被自动从队列中移除
- ✅ **详细错误信息**: 超时错误包含实际等待时间和超时限制
- ✅ **日志记录**: 超时事件会被记录到日志中,方便监控
- ✅ **零性能开销**: 仅在处理批次时检查,不影响正常请求性能

## 配置方法

### 环境变量

```bash
# 设置队列超时时间为 60 秒
export INFINITY_QUEUE_TIMEOUT=60

# 设置队列超时时间为 5 分钟 (默认值为 300 秒)
export INFINITY_QUEUE_TIMEOUT=300

# 设置队列超时时间为 10 分钟
export INFINITY_QUEUE_TIMEOUT=600
```

### 启动服务

```bash
# 使用默认超时 (300秒)
infinity_emb v2 --model-id BAAI/bge-small-en-v1.5

# 使用自定义超时
INFINITY_QUEUE_TIMEOUT=60 infinity_emb v2 --model-id BAAI/bge-small-en-v1.5
```

## 使用场景

### 1. 高并发场景

在高并发场景下,队列可能会积压大量请求。设置合理的超时时间可以:
- 避免客户端长时间等待
- 快速失败,让客户端可以重试或降级处理
- 防止资源耗尽

```bash
# 高并发场景建议设置较短的超时
export INFINITY_QUEUE_TIMEOUT=30  # 30秒
```

### 2. 批处理场景

对于批处理任务,可以设置较长的超时时间:

```bash
# 批处理场景可以设置较长的超时
export INFINITY_QUEUE_TIMEOUT=600  # 10分钟
```

### 3. 实时服务

实时服务需要快速响应,建议设置较短的超时:

```bash
# 实时服务建议设置短超时
export INFINITY_QUEUE_TIMEOUT=10  # 10秒
```

## 客户端处理

### Python 客户端示例

```python
import asyncio
from infinity_emb import AsyncEmbeddingEngine
from infinity_emb.args import EngineArgs

async def embed_with_retry(engine, sentences, max_retries=3):
    """带重试的 embedding 请求"""
    for attempt in range(max_retries):
        try:
            embeddings, usage = await engine.embed(sentences=sentences)
            return embeddings, usage
        except TimeoutError as e:
            print(f"Request timed out (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # 等待后重试
            else:
                raise
        except Exception as e:
            print(f"Other error: {e}")
            raise

# 使用示例
async def main():
    engine = AsyncEmbeddingEngine.from_args(
        EngineArgs(model_name_or_path="BAAI/bge-small-en-v1.5")
    )
    
    await engine.astart()
    
    try:
        sentences = ["Hello world", "How are you?"]
        embeddings, usage = await embed_with_retry(engine, sentences)
        print(f"Success! Got {len(embeddings)} embeddings")
    except TimeoutError:
        print("Request failed after all retries")
    finally:
        await engine.astop()

asyncio.run(main())
```

### HTTP API 客户端示例

```python
import requests
import time

def embed_with_retry(url, data, max_retries=3, timeout=30):
    """HTTP API 带重试的请求"""
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{url}/embeddings",
                json=data,
                timeout=timeout
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # 队列过载,等待后重试
                print(f"Queue overloaded (attempt {attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)  # 指数退避
            else:
                response.raise_for_status()
                
        except requests.exceptions.Timeout:
            print(f"Request timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise
    
    raise Exception("Failed after all retries")

# 使用示例
result = embed_with_retry(
    url="http://localhost:7997",
    data={
        "model": "BAAI/bge-small-en-v1.5",
        "input": ["Hello world", "How are you?"]
    }
)
print(result)
```

## 监控和日志

### 日志示例

当请求超时时,会在日志中看到类似以下信息:

```
WARNING - [⏱️] Dropped 5 request(s) due to queue timeout (limit: 300s)
```

### 监控指标

可以通过 `/models` 端点监控队列状态:

```python
import requests

response = requests.get("http://localhost:7997/models")
stats = response.json()['data'][0]['stats']

print(f"Queue usage: {stats['queue_absolute']}")
print(f"Queue fraction: {stats['queue_fraction']:.2%}")
print(f"Results pending: {stats['results_pending']}")
```

## 最佳实践

### 1. 合理设置超时时间

- **计算公式**: `timeout = 平均处理时间 × 队列大小 / 批次大小 × 安全系数`
- **安全系数**: 建议设置为 2-3 倍

示例:
```
平均处理时间: 100ms
队列大小: 32000
批次大小: 32
安全系数: 2

timeout = 0.1s × 32000 / 32 × 2 = 200s
```

### 2. 配合队列大小使用

```bash
# 队列大小和超时时间应该配合设置
export INFINITY_QUEUE_SIZE=16000
export INFINITY_QUEUE_TIMEOUT=120
```

### 3. 监控和告警

建议设置监控告警:
- 当超时请求数量超过阈值时告警
- 当队列使用率持续超过 80% 时告警

### 4. 客户端重试策略

- 使用指数退避策略
- 设置最大重试次数
- 记录失败请求用于分析

## 技术细节

### 实现原理

1. **时间戳记录**: 请求入队时记录 `enqueue_time`
2. **批次处理时检查**: 在 `pop_optimal_batches` 时检查每个请求的等待时间
3. **超时处理**: 对超时请求设置 `TimeoutError` 异常并从队列中移除
4. **日志记录**: 统计并记录超时请求数量

### 性能影响

- **CPU 开销**: 极小,仅在批次处理时进行时间比较
- **内存开销**: 每个请求增加 8 字节 (float64 时间戳)
- **延迟影响**: 无,不影响正常请求的处理延迟

### 相关配置

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `INFINITY_QUEUE_TIMEOUT` | 300 | 队列超时时间(秒) |
| `INFINITY_QUEUE_SIZE` | 32000 | 最大队列大小 |
| `INFINITY_BATCH_SIZE` | 32 | 批处理大小 |

## 测试

运行测试脚本验证功能:

```bash
# 设置短超时用于测试
export INFINITY_QUEUE_TIMEOUT=5

# 运行测试
python test_queue_timeout.py
```

## 故障排查

### 问题: 大量请求超时

**可能原因**:
1. 超时时间设置过短
2. 队列积压严重
3. 模型处理速度慢

**解决方案**:
1. 增加 `INFINITY_QUEUE_TIMEOUT`
2. 增加 `INFINITY_BATCH_SIZE` 提高吞吐量
3. 增加 GPU 资源或使用更快的模型
4. 横向扩展,部署多个实例

### 问题: 没有超时发生

**可能原因**:
1. 超时时间设置过长
2. 请求处理速度快,没有积压

**解决方案**:
1. 减小 `INFINITY_QUEUE_TIMEOUT` (如果需要更快失败)
2. 这是正常现象,说明系统运行良好

## 版本历史

- **v0.0.77+**: 添加队列超时功能

## 相关文档

- [环境变量配置](../docs/env_variables.md)
- [性能调优指南](../docs/performance_tuning.md)
- [监控和告警](../docs/monitoring.md)
