import _collections
import System

class Cache:
    """A generic cache implementation that can be subclassed with a caching strategy."""
    def __init__(self):
        self._cache = {}

    def __getitem__(self, _key):
        """Returns the cached value of the given key.

        Args:
            _key (Any): cached key
        Returns:
            value (Any): cached value
        Raises:
            KeyError: if key is not present
            NotImplementedError: if the validation method is not defined.
        """
        if not self._isValid(_key):
            raise KeyError(_key)
        return self._cache[_key]

    def __setitem__(self, _key, _value):
        self._cache[_key] = _value

    def __delitem__(self, _key):
        self._cache.pop(_key)

    def __repr__(self):
        return JsonHelper.Serialize(self._cache)

    def _isValid(self, _key):
        raise NotImplementedError

    def _removeInvalid(self):
        """Remove all invalid key value pairs"""
        for value in self._cache.values():
            if not self._isValid(value):
                self._cache.pop(value)

    def __len__(self):
        return len(self._cache)

    def clear(self):
        """Clear all key value pairs from the cache."""
        try:
            while True:
                self._cache.popitem()
        except KeyError:
            pass

class DatabaseCache(Cache):
    """A cache that returns values until the time-to-live (TTL) has passed.

    Uses deque for O(1) add & FIFO removal.
    Expired entries may stay in memory until a new item is added, but won't be returned.
    """

    def __init__(self, _time_to_live):
        Cache.__init__(self)

        if not isinstance(_time_to_live, System.TimeSpan):
            raise ValueError("Expected System.TimeSpan")
        self._time_to_live = _time_to_live
        self._history = _collections.deque()

    def __getitem__(self, _key):
        item = Cache.__getitem__(self, _key)
        return item["value"]

    def _isValid(self, _key):
        return not self.hasExpired(self._cache[_key]["date"])

    def _removeInvalid(self):
        """Remove expired items (oldest first)."""
        if not self._history:
            return
        while len(self._history) > 0:
            oldest = self._history[-1]  # rightmost = oldest (FIFO)
            if not self.hasExpired(oldest["date"]):
                break
            self._cache.pop(oldest["key"])
            self._history.pop()

    def __setitem__(self, _key, _value):
        """Store the key value pair in the cache.
        Removes all invalid pairs before adding the value.
        """
        is_new = _key not in self._cache
        if not is_new:
            # update is not considered for performance reasons
            # if update is required, delete key before reading
            # entry expires after TTL regardless of usage after insertion
            return
        self._removeInvalid()
        now = DateTime.UtcNow
        item = {"value": _value, "date": now}
        Cache.__setitem__(self, _key, item)
        self._history.appendleft({"key": _key, "date": now})

    def hasExpired(self, _date_time):
        """Indicate whether the date exceeds the allowed time-to-live.

        Args:
            _date_time (DateTime): the date time in Utc
        """
        if not _date_time:
            return True
        return bool((DateTime.UtcNow - _date_time) > self._time_to_live)

    def clear(self):
        """Clear all key value pairs from the cache and history."""
        Cache.clear(self)
        self._history.clear()

    def __delitem__(self, _key):
        self._cache.pop(_key)
        self._history = _collections.deque(item for item in self._history if item["key"] != _key)
