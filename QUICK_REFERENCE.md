# 队列超时功能 - 快速参考

## 一句话说明
自动清理在队列中等待时间过长的请求,防止无限期等待。

## 快速开始

### 1. 配置超时时间
```bash
export INFINITY_QUEUE_TIMEOUT=60  # 60秒超时
```

### 2. 启动服务
```bash
infinity_emb v2 --model-id BAAI/bge-small-en-v1.5
```

### 3. 处理超时异常
```python
try:
    embeddings, usage = await engine.embed(sentences=sentences)
except TimeoutError as e:
    print(f"Timeout: {e}")
```

## 常用配置

| 场景 | 超时时间 | 命令 |
|------|---------|------|
| 实时服务 | 10秒 | `export INFINITY_QUEUE_TIMEOUT=10` |
| 通用服务 | 60秒 | `export INFINITY_QUEUE_TIMEOUT=60` |
| 批处理 | 10分钟 | `export INFINITY_QUEUE_TIMEOUT=600` |
| 默认 | 5分钟 | (不设置,使用默认值) |

## 重试模板

```python
async def embed_with_retry(engine, sentences, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await engine.embed(sentences=sentences)
        except TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise
```

## 监控命令

```bash
# 查看队列状态
curl http://localhost:7997/models | jq '.data[0].stats'

# 查看日志中的超时事件
tail -f logs/infinity.log | grep "⏱️"
```

## 计算超时时间

```
timeout = 平均处理时间 × 队列大小 / 批次大小 × 2

示例: 0.1s × 32000 / 32 × 2 = 200s
```

## 故障排查

### 大量超时?
1. 增加超时: `export INFINITY_QUEUE_TIMEOUT=300`
2. 增加批次: `export INFINITY_BATCH_SIZE=64`
3. 扩展实例

### 没有超时?
- 正常现象,系统运行良好
- 如需更快失败,减小超时值

## 相关文件

- 📖 详细文档: `QUEUE_TIMEOUT_FEATURE.md`
- 🧪 测试脚本: `test_queue_timeout.py`
- 💡 使用示例: `example_queue_timeout.py`
- 📝 实现总结: `IMPLEMENTATION_SUMMARY.md`
- 📋 变更日志: `CHANGELOG_QUEUE_TIMEOUT.md`

## 关键点

✅ 默认 300 秒超时
✅ 零性能开销
✅ 自动清理超时请求
✅ 详细错误信息
✅ 日志记录
✅ 向后兼容

---
**版本**: 0.0.77+ | **日期**: 2025-12-04
