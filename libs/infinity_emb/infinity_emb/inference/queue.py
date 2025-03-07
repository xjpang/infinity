# SPDX-License-Identifier: MIT
# Copyright (c) 2023-now michaelfeil

import asyncio
import os
import threading
import time
from typing import Generator, Optional

from infinity_emb.inference.caching_layer import Cache
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
        self.timeout = int(os.getenv('INFINITY_REQUEST_TIMEOUT', '0'))  # ms

    def __len__(self):
        return len(self._queue)

    def extend(self, items: list[PrioritizedQueueItem]):
        with self._lock_queue_event:
            # TODO: _lock event might be conjesting the main thread.
            self._queue.extend(items)
        self._sync_event.set()

    def pop_optimal_batches(
            self, size: int, max_n_batches: int = 4, timeout=0.2, **kwargs
    ) -> Generator[list[QueueItemInner], None, None]:
        """
        pop batch `up to size` + `continuous (sorted)` from queue

        Args:
            size (int): max size of batch
            max_n_batches: number of batches to be popped and sorted.
            timeout (float, optional): timeout until None is returned. Defaults to 0.2.
            latest_first (bool, optional): guarantees processing of oldest item in list.
                As latest first requires getting argmin of created timestamps,
                which is slow.  Defaults to False.

        returns:
            None: if there is not a single item in self._queue after timeout
            else: list[EmbeddingInner] with len(1<=size)
        """
        self.clear_timeout_item(self.timeout)

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

        new_items: list[QueueItemInner] = [
            mi.item for mi in new_items_l if not mi.item.future.done()
        ]

        for i in range(0, len(new_items), size):
            yield new_items[i: i + size]

    def clear_timeout_item(self, timeout: int):
        if self.timeout == 0 or not self._queue:
            return

        cur_timestamp = int(time.time() * 1000)
        with (self._lock_queue_event):
            for queue_item in self._queue:
                if queue_item.item.content.create_timestamp < cur_timestamp and (
                        cur_timestamp - queue_item.item.content.create_timestamp) > timeout:
                    queue_item.item.timeout()
                else:
                    break


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
