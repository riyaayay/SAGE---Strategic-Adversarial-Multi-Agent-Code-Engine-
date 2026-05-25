```python
import threading
from collections import deque, defaultdict

class LRUCache:
    def __init__(self, max_size):
        self.max_size = max_size
        self.cache_store = {}
        self.lru_queue = deque()
        self.ttl_dict = defaultdict(int)
        self.lock = threading.Lock()

    def set(self, key, value, ttl):
        with self.lock:
            if key in self.cache_store:
                # Update the access time and TTL
                self.lru_queue.remove(key)
                self.lru_queue.append(key)
                self.ttl_dict[key] = ttl + self.get_current_time()
            else:
                # Add a new item to the cache store, LRU queue, and TTL dictionary
                if len(self.cache_store) >= self.max_size:
                    self.delete_lru_item()
                self.cache_store[key] = value
                self.lru_queue.append(key)
                self.ttl_dict[key] = ttl + self.get_current_time()

    def get(self, key):
        with self.lock:
            if key in self.cache_store and self.is_within_ttl(key):
                # Update the access time
                self.lru_queue.remove(key)
                self.lru_queue.append(key)
                return self.cache_store[key]
            else:
                return None

    def delete(self, key):
        with self.lock:
            if key in self.cache_store:
                del self.cache_store[key]
                self.lru_queue.remove(key)
                del self.ttl_dict[key]

    def clear(self):
        with self.lock:
            self.cache_store.clear()
            self.lru_queue.clear()
            self.ttl_dict.clear()

    def delete_lru_item(self):
        if not self.lru_queue:
            return
        key = self.lru_queue.popleft()
        del self.cache_store[key]
        del self.ttl_dict[key]

    def is_within_ttl(self, key):
        current_time = self.get_current_time()
        return current_time < self.ttl_dict[key]

    def get_current_time(self):
        # Return the current time in seconds since epoch
        import time
        return int(time.time())
```