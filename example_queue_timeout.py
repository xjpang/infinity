#!/usr/bin/env python3
"""
简单示例: 演示队列超时功能的基本使用

这个示例展示了:
1. 如何配置队列超时
2. 如何处理超时异常
3. 如何实现重试逻辑
"""

import asyncio
import os


async def simple_example():
    """最简单的使用示例"""
    from infinity_emb import AsyncEmbeddingEngine
    from infinity_emb.args import EngineArgs
    
    print("=" * 60)
    print("简单示例: 基本使用")
    print("=" * 60)
    
    # 创建引擎
    engine = AsyncEmbeddingEngine.from_args(
        EngineArgs(model_name_or_path="michaelfeil/bge-small-en-v1.5")
    )
    
    await engine.astart()
    
    try:
        # 正常请求
        sentences = ["Hello world", "How are you?"]
        embeddings, usage = await engine.embed(sentences=sentences)
        print(f"\n✓ 成功获取 {len(embeddings)} 个 embeddings")
        print(f"  Token 使用量: {usage}")
        
    except TimeoutError as e:
        print(f"\n✗ 请求超时: {e}")
    finally:
        await engine.astop()


async def retry_example():
    """带重试逻辑的示例"""
    from infinity_emb import AsyncEmbeddingEngine
    from infinity_emb.args import EngineArgs
    
    print("\n" + "=" * 60)
    print("高级示例: 带重试逻辑")
    print("=" * 60)
    
    async def embed_with_retry(engine, sentences, max_retries=3):
        """带指数退避的重试逻辑"""
        for attempt in range(max_retries):
            try:
                embeddings, usage = await engine.embed(sentences=sentences)
                return embeddings, usage
            except TimeoutError as e:
                wait_time = 2 ** attempt  # 指数退避: 1s, 2s, 4s
                print(f"\n  尝试 {attempt + 1}/{max_retries} 失败: {e}")
                
                if attempt < max_retries - 1:
                    print(f"  等待 {wait_time}s 后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"  所有重试都失败了")
                    raise
    
    engine = AsyncEmbeddingEngine.from_args(
        EngineArgs(model_name_or_path="michaelfeil/bge-small-en-v1.5")
    )
    
    await engine.astart()
    
    try:
        sentences = ["This is a test", "Another test sentence"]
        embeddings, usage = await embed_with_retry(engine, sentences)
        print(f"\n✓ 成功获取 {len(embeddings)} 个 embeddings")
        
    except TimeoutError:
        print("\n✗ 请求最终失败")
    finally:
        await engine.astop()


async def check_configuration():
    """检查当前配置"""
    from infinity_emb.env import MANAGER
    
    print("\n" + "=" * 60)
    print("当前配置")
    print("=" * 60)
    
    print(f"\n队列配置:")
    print(f"  INFINITY_QUEUE_TIMEOUT: {MANAGER.queue_timeout}s")
    print(f"  INFINITY_QUEUE_SIZE: {MANAGER.queue_size}")
    
    print(f"\n环境变量设置方法:")
    print(f"  export INFINITY_QUEUE_TIMEOUT=60   # 60秒超时")
    print(f"  export INFINITY_QUEUE_SIZE=16000   # 队列大小")


async def http_client_example():
    """HTTP 客户端示例"""
    print("\n" + "=" * 60)
    print("HTTP 客户端示例")
    print("=" * 60)
    
    print("""
使用 requests 库的示例代码:

```python
import requests
import time

def embed_with_retry(url, data, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{url}/embeddings",
                json=data,
                timeout=30  # HTTP 超时
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # 队列过载,等待后重试
                print(f"队列过载,等待重试...")
                time.sleep(2 ** attempt)
            else:
                response.raise_for_status()
                
        except requests.exceptions.Timeout:
            print(f"请求超时 (尝试 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise
    
    raise Exception("所有重试都失败了")

# 使用
result = embed_with_retry(
    url="http://localhost:7997",
    data={
        "model": "BAAI/bge-small-en-v1.5",
        "input": ["Hello world"]
    }
)
```
""")


def main():
    """主函数"""
    print("\n🚀 队列超时功能示例\n")
    
    # 显示当前配置
    asyncio.run(check_configuration())
    
    # 简单示例
    asyncio.run(simple_example())
    
    # 重试示例
    asyncio.run(retry_example())
    
    # HTTP 客户端示例
    asyncio.run(http_client_example())
    
    print("\n" + "=" * 60)
    print("💡 提示")
    print("=" * 60)
    print("""
1. 设置较短的超时用于测试:
   export INFINITY_QUEUE_TIMEOUT=5

2. 查看更多示例:
   - 功能文档: QUEUE_TIMEOUT_FEATURE.md
   - 测试脚本: test_queue_timeout.py
   - 实现总结: IMPLEMENTATION_SUMMARY.md

3. 监控队列状态:
   curl http://localhost:7997/models
""")
    
    print("\n✅ 示例完成!\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  示例被用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
