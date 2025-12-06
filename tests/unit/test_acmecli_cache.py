"""
Unit tests for acmecli cache module
"""
import pytest
from src.acmecli.cache import InMemoryCache


class TestInMemoryCache:
    """Test InMemoryCache class"""

    def test_module_import(self):
        """Test that module can be imported correctly"""
        import src.acmecli.cache
        assert hasattr(src.acmecli.cache, 'InMemoryCache')
        assert src.acmecli.cache.InMemoryCache is InMemoryCache

    def test_cache_initialization(self):
        """Test cache initialization"""
        cache = InMemoryCache()
        assert cache._cache == {}
        assert cache._etags == {}

    def test_cache_set_and_get(self):
        """Test setting and getting cached data"""
        cache = InMemoryCache()
        data = b"test data"
        cache.set("key1", data)
        assert cache.get("key1") == data

    def test_cache_get_missing_key(self):
        """Test getting non-existent key returns None"""
        cache = InMemoryCache()
        assert cache.get("non_existent") is None

    def test_cache_set_with_etag(self):
        """Test setting cache with etag"""
        cache = InMemoryCache()
        data = b"test data"
        etag = "etag123"
        cache.set("key1", data, etag=etag)
        assert cache.get("key1") == data
        assert cache.get_etag("key1") == etag

    def test_cache_set_without_etag(self):
        """Test setting cache without etag"""
        cache = InMemoryCache()
        data = b"test data"
        cache.set("key1", data)
        assert cache.get("key1") == data
        assert cache.get_etag("key1") is None

    def test_cache_get_etag_missing_key(self):
        """Test getting etag for non-existent key returns None"""
        cache = InMemoryCache()
        assert cache.get_etag("non_existent") is None

    def test_cache_overwrite(self):
        """Test overwriting existing cache entry"""
        cache = InMemoryCache()
        cache.set("key1", b"old data")
        cache.set("key1", b"new data")
        assert cache.get("key1") == b"new data"

    def test_cache_overwrite_etag(self):
        """Test overwriting etag for existing entry"""
        cache = InMemoryCache()
        cache.set("key1", b"data", etag="old_etag")
        cache.set("key1", b"data", etag="new_etag")
        assert cache.get_etag("key1") == "new_etag"

    def test_cache_multiple_keys(self):
        """Test caching multiple keys"""
        cache = InMemoryCache()
        cache.set("key1", b"data1", etag="etag1")
        cache.set("key2", b"data2", etag="etag2")
        assert cache.get("key1") == b"data1"
        assert cache.get("key2") == b"data2"
        assert cache.get_etag("key1") == "etag1"
        assert cache.get_etag("key2") == "etag2"

    def test_cache_empty_bytes(self):
        """Test caching empty bytes"""
        cache = InMemoryCache()
        cache.set("key1", b"")
        assert cache.get("key1") == b""

