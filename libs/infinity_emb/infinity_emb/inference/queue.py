# SPDX-License-Identifier: MIT
# Copyright (c) 2023-now michaelfeil

import asyncio
import threading
from typing import Optional, Generator

from infinity_emb.inference.caching_layer import Cache
from infinity_emb.log_handler import logger
from infinity_emb.primitives import (
    EmbeddingReturnType,
    PrioritizedQueueItem,
    QueueItemInner,
)


class CustomFIFOQueue:
    """Class which defines a custom ordering"""

    def __init__(self) -> None:
        """"""
        self._lock_queue_event = threading.Lock()
        self._queue: list[PrioritizedQueueItem] = []
        # event that indicates items in queue.
        self._sync_event = threading.Event()

    def __len__(self):
        return len(self._queue)

    def extend(self, items: list[PrioritizedQueueItem]):
        with self._lock_queue_event:
            # TODO: _lock event might be conjesting the main thread.
            self._queue.extend(items)
        self._sync_event.set()

    def _purge_timed_out_requests(self, queue_timeout: float) -> int:
        """
        Purge all timed-out requests from the entire queue before popping batches.
        This ensures that the batch size remains stable by removing expired requests upfront.
        
        Args:
            queue_timeout: max time a request can wait in queue before being dropped.
            
        Returns:
            int: number of requests that were purged due to timeout
        """
        import time
        current_time = time.time()
        timeout_count = 0
        
        with self._lock_queue_event:
            valid_items: list[PrioritizedQueueItem] = []
            for item in self._queue:
                # Skip if future is already done
                if item.item.future.done():
                    continue
                    
                # Check if request has timed out
                if item.enqueue_time > 0:
                    wait_time = current_time - item.enqueue_time
                    if wait_time > queue_timeout:
                        # Cancel the future with timeout error
                        timeout_count += 1
                        try:
                            item.item.future.set_exception(
                                TimeoutError(f"Request timed out after {wait_time:.2f}s in queue (limit: {queue_timeout}s)")
                            )
                        except asyncio.exceptions.InvalidStateError:
                            pass
                        continue
                
                valid_items.append(item)
            
            self._queue = valid_items
            if not self._queue:
                self._sync_event.clear()
        
        return timeout_count

    def pop_optimal_batches(
        self, size: int, max_n_batches: int = 4, timeout=0.2, queue_timeout: Optional[float] = None, **kwargs
    ) -> Generator[list[QueueItemInner], None, None]:
        """
        pop batch `up to size` + `continuous (sorted)` from queue

        Args:
            size (int): max size of batch
            max_n_batches: number of batches to be popped and sorted.
            timeout (float, optional): timeout until None is returned. Defaults to 0.2.
            queue_timeout (float, optional): max time a request can wait in queue before being dropped.
            latest_first (bool, optional): guarantees processing of oldest item in list.
                As latest first requires getting argmin of created timestamps,
                which is slow.  Defaults to False.

        returns:
            None: if there is not a single item in self._queue after timeout
            else: list[EmbeddingInner] with len(1<=size)
        """
        # Purge timed-out requests from the entire queue first
        # This ensures batch size stability by removing expired requests upfront
        if queue_timeout is not None and queue_timeout > 0:
            timeout_count = self._purge_timed_out_requests(queue_timeout)
            if timeout_count > 0:
                logger.warning(
                    f"[⏱️] Purged {timeout_count} request(s) due to queue timeout (limit: {queue_timeout}s)"
                )

        if not self._queue:
            if not self._sync_event.wait(timeout):
                return

        # Determine the number of batches to process
        # n_batches = min(max_n_batches, max(1, len(self._queue) // size))
        size_batches = size * max_n_batches

        with self._lock_queue_event:
            new_items_l = self._queue[:size_batches]
            self._queue = self._queue[size_batches:]
            if not self._queue:
                self._sync_event.clear()

        if len(new_items_l) > size:
            # Sort the items for optimal batching
            new_items_l.sort()

        # Extract the inner items (no need to filter again since we already purged)
        new_items: list[QueueItemInner] = []
        for mi in new_items_l:
            # Skip if future is already done (could happen due to race condition)
            if mi.item.future.done():
                continue
            new_items.append(mi.item)

        for i in range(0, len(new_items), size):
            yield new_items[i : i + size]


class ResultKVStoreFuture:
    def __init__(self, cache: Optional[Cache] = None) -> None:
        """holds instance of Cache"""
        self._cache = cache

    def __len__(self):
        """deprecated"""
        return 0  # len(self._kv)

    async def wait_for_response(self, item: QueueItemInner) -> EmbeddingReturnType:
        """wait for future to return"""
        if self._cache:
            asyncio.create_task(self._cache.aget_complete(item))
        return await item.future
