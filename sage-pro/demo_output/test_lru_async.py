```python
import pytest
from concurrent.futures import ThreadPoolExecutor

@pytest.fixture
def cache():
    return LRUCache(3)

@pytest.mark.parametrize("key, value, ttl", [
    ("a", 10, 5),
    ("b", 20, 7),
    ("c", 30, 9)
])
def test_set(cache, key, value, ttl):
    cache.set(key, value, ttl)
    assert cache.cache_store[key] == value
    assert cache.ttl_dict[key] == ttl + 5

@pytest.mark.parametrize("key", ["a", "b", "c"])
def test_get(cache, key):
    cache.set(key, 10, 5)
    assert cache.get(key) == 10
    cache.delete(key)
    assert cache.get(key) is None

@pytest.mark.parametrize("key", ["a", "b", "c"])
def test_delete(cache, key):
    cache.set(key, 10, 5)
    cache.delete(key)
    assert key not in cache.cache_store
    assert key not in cache.ttl_dict

@pytest.mark.parametrize("key", ["a", "b", "c"])
def test_clear(cache, key):
    cache.set(key, 10, 5)
    cache.clear()
    assert len(cache.cache_store) == 0
    assert len(cache.ttl_dict) == 0

@pytest.mark.asyncio
async def test_async_eviction(cache):
    with ThreadPoolExecutor() as executor:
        # Simulate setting items concurrently
        futures = [executor.submit(cache.set, key, value, ttl) for key, value, ttl in [
            ("a", 10, 5),
            ("b", 20, 7),
            ("c", 30, 9)
        ]]
        await asyncio.gather(*futures)

    # Wait for a bit to allow the cache to evict items
    import time
    time.sleep(1)

    assert len(cache.cache_store) == 2
    assert "a" in cache.cache_store and "b" in cache.cache_store
    assert "c" not in cache.cache_store

# Edge cases
def test_edge_cases(cache):
    with pytest.raises(KeyError):
        cache.get("d")

    with pytest.raises(KeyError):
        cache.delete("d")

    # Test concurrent access to the same key
    def set_and_get(key, value, ttl):
        cache.set(key, value, ttl)
        assert cache.get(key) == value

    executor = ThreadPoolExecutor()
    futures = [executor.submit(set_and_get, key, value, ttl) for key, value, ttl in [
        ("a", 10, 5),
        ("b", 20, 7),
        ("c", 30, 9)
    ]]
    executor.shutdown(wait=False)

    # Wait for a bit to allow the cache to evict items
    import time
    time.sleep(1)

    assert len(cache.cache_store) == 2
    assert "a" in cache.cache_store and "b" in cache.cache_store
    assert "c" not in cache.cache_store

# Error handling strategy
def test_error_handling(cache):
    with pytest.raises(KeyError):
        cache.get("d")

    with pytest.raises(KeyError):
        cache.delete("d")

    # Test concurrent access to the same key
    def set_and_get(key, value, ttl):
        cache.set(key, value, ttl)
        assert cache.get(key) == value

    executor = ThreadPoolExecutor()
    futures = [executor.submit(set_and_get, key, value, ttl) for key, value, ttl in [
        ("a", 10, 5),
        ("b", 20, 7),
        ("c", 30, 9)
    ]]
    executor.shutdown(wait=False)

    # Wait for a bit to allow the cache to evict items
    import time
    time.sleep(1)

    assert len(cache.cache_store) == 2
    assert "a" in cache.cache_store and "b" in cache.cache_store
    assert "c" not in cache.cache_store
```