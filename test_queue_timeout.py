#!/usr/bin/env python3
"""
Test script for queue timeout functionality.

This script tests the new INFINITY_QUEUE_TIMEOUT feature that automatically
drops requests that have been waiting in the queue for too long.

Usage:
    # Set a short timeout for testing (e.g., 5 seconds)
    export INFINITY_QUEUE_TIMEOUT=5
    
    # Run the test
    python test_queue_timeout.py
"""

import asyncio
import time
from infinity_emb.args import EngineArgs
from infinity_emb.engine import AsyncEmbeddingEngine
from infinity_emb.primitives import InferenceEngine


async def test_queue_timeout():
    """Test that requests timeout correctly when waiting too long in queue."""
    
    print("=" * 60)
    print("Testing Queue Timeout Functionality")
    print("=" * 60)
    
    # Create engine with small batch size to force queueing
    engine_args = EngineArgs(
        model_name_or_path="michaelfeil/bge-small-en-v1.5",
        batch_size=2,  # Small batch size
        engine=InferenceEngine.torch,
    )
    
    engine = AsyncEmbeddingEngine.from_args(engine_args)
    
    try:
        await engine.astart()
        
        # Check the configured timeout
        timeout_value = engine._batch_handler._queue_timeout
        print(f"\n✓ Queue timeout configured: {timeout_value}s")
        
        # Create a large number of requests to fill the queue
        sentences = [f"This is test sentence number {i}" for i in range(100)]
        
        print(f"\n📝 Submitting {len(sentences)} requests...")
        print(f"   (with batch_size={engine_args.batch_size}, this will take time)")
        
        start_time = time.time()
        
        # Submit all requests at once
        tasks = []
        for sentence in sentences:
            task = engine.embed(sentences=[sentence])
            tasks.append(task)
        
        # Wait for all to complete (some may timeout)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        # Count successes and timeouts
        successes = sum(1 for r in results if not isinstance(r, Exception))
        timeouts = sum(1 for r in results if isinstance(r, TimeoutError))
        other_errors = sum(1 for r in results if isinstance(r, Exception) and not isinstance(r, TimeoutError))
        
        print(f"\n📊 Results after {elapsed:.2f}s:")
        print(f"   ✓ Successful: {successes}")
        print(f"   ⏱️  Timed out: {timeouts}")
        print(f"   ❌ Other errors: {other_errors}")
        
        if timeouts > 0:
            print(f"\n✅ Queue timeout is working! {timeouts} requests were dropped.")
            # Show a sample timeout error
            for r in results:
                if isinstance(r, TimeoutError):
                    print(f"\n   Sample timeout error: {r}")
                    break
        else:
            print(f"\n⚠️  No timeouts occurred. Try:")
            print(f"   - Setting a shorter INFINITY_QUEUE_TIMEOUT")
            print(f"   - Increasing the number of test requests")
            print(f"   - Reducing batch_size further")
        
    finally:
        await engine.astop()
        print("\n" + "=" * 60)


async def test_timeout_configuration():
    """Test that timeout can be configured via environment variable."""
    import os
    from infinity_emb.env import MANAGER
    
    print("\n" + "=" * 60)
    print("Testing Timeout Configuration")
    print("=" * 60)
    
    # Show current configuration
    timeout = MANAGER.queue_timeout
    queue_size = MANAGER.queue_size
    
    print(f"\n📋 Current Configuration:")
    print(f"   INFINITY_QUEUE_TIMEOUT: {timeout}s")
    print(f"   INFINITY_QUEUE_SIZE: {queue_size}")
    
    print(f"\n💡 To change timeout, set environment variable:")
    print(f"   export INFINITY_QUEUE_TIMEOUT=60  # 60 seconds")
    print(f"   export INFINITY_QUEUE_TIMEOUT=300 # 5 minutes (default)")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("\n🚀 Starting Queue Timeout Tests\n")
    
    # Test configuration
    asyncio.run(test_timeout_configuration())
    
    # Test actual timeout behavior
    print("\n⚠️  Note: The following test may take several minutes to complete.")
    print("   It will submit many requests to trigger queue timeouts.\n")
    
    try:
        asyncio.run(test_queue_timeout())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    
    print("\n✅ All tests completed!\n")
