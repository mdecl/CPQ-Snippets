import re
import Scripting
import System
import Decorators

class DbType:
    """Database table column data type enum"""
    BIT = Scripting.SqlDbType.Bit
    DATE = Scripting.SqlDbType.Date
    DATETIME = Scripting.SqlDbType.DateTime
    DECIMAL = Scripting.SqlDbType.Decimal
    INT = Scripting.SqlDbType.Int
    NVARCHAR = Scripting.SqlDbType.NVarChar

class Cache:
    """A generic cache implementation that can be subclassed with a caching strategy."""
    def __init__(self):
        self._cache = {}

    def __getitem__(self, key):
        """Returns the cached value of the given key.

        Args:
            key (Any): cached key
        Returns:
            value (Any): cached value
        Raises:
            KeyError: if key is not present
            NotImplementedError: if the validation method is not defined.
        """
        if not self._is_valid(key):
            raise KeyError(key)
        return self._cache[key]

    def __setitem__(self, key, value):
        self._cache[key] = value

    def __delitem__(self, key):
        self._cache.pop(key)

    def __repr__(self):
        return JsonHelper.Serialize(self._cache)

    def _is_valid(self, key):
        raise NotImplementedError

    def _remove_invalid(self):
        """Remove all invalid key value pairs"""
        for value in self._cache.values():
            if not self._is_valid(value):
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
    """A cache that will return the stored values until the given time-to-live (TTL) has passed.

    Uses First In First Out (FIFO) to remove items.
    Expired entries may stay in memory until a new item is added, but will not be returned.
    """

    def __init__(self, time_to_live):
        Cache.__init__(self)

        if not isinstance(time_to_live, System.TimeSpan):
            raise ValueError("Expected System.TimeSpan")
        self.__time_to_live = time_to_live
        self.__history = []

    def __getitem__(self, key):
        item = Cache.__getitem__(self, key)
        return item["value"]

    def _is_valid(self, key):
        return not self.has_expired(self._cache[key]["date"])

    def _remove_invalid(self):
        if not self.__history:
            return
        while len(self.__history) > 0:
            oldest = self.__history[-1]
            if not self.has_expired(oldest["date"]):
                break
            self._cache.pop(oldest["key"])
            self.__history.pop()

    def __setitem__(self, key, value):
        """Store the key value pair in the cache.
        Removes all invalid pairs before adding the value.
        """
        self._remove_invalid()
        is_new = key not in self._cache
        now = DateTime.UtcNow
        item = {"value": value, "date": now}
        Cache.__setitem__(self, key, item)
        if not is_new:
            # date was updated on the existing stored item
            return
        self.__history.insert( 0, {"key": key, "date": now})

    def has_expired(self, date_time):
        """Indicate whether the date exceeds the allowed time-to-live.

        Args:
            date_time (DateTime): the date time in Utc
        Returns:
            is_expired (bool): boolean
        """
        if not date_time:
            return True
        return bool((DateTime.UtcNow - date_time) > self.__time_to_live)

def unpack_tuple_argument(func):
    """ Decorator to equalize 1 tuple with args or multiple *args
        - option 1: _func( arg1, arg2, arg3)
        - option 2: _func((arg1, arg2, arg3))
    """
    @Decorators.wraps(func)
    def wrapper(query, *params):
        if len(params) == 1 and isinstance(params[0], tuple):
            params = params[0]
        return func(query, *params)
    return wrapper

class SqlWrapper:
    """Wrapper for CPQ's SqlHelper.

    Features:
    --------
    -   Easier creation and usage of sql parameters.
    -   Caching of query results.
    -   Tracing of query, params and result.

    Purpose:
    --------
    -   Abstracts parameter handling and result mapping to prevent SQL injection and 
        conversion errors.
    -   Improves code readability and accessibility of CPQ's built-in SQL Parameters.
    -   Extended tracing removes the need for individual tracing of lookup results.
    -   Class methods provide access to the functionality without instantiating the class.
    -   Limit the number of database lookups to prevent database reader timeouts.

    Caching use case:
    --------
    -   Some scenarios trigger the same events multiple times in a short period.
        Each event triggers a database lookup with the same query and parameters.
    -   Similarly, sometimes the same lookup can be executed on different events in a short period.
    -   Removes the need for (possibly inconsistent) cache implementations on other classes by 
        putting it in one place, without requiring the cache implementation details
        as the same query can just be executed again.

    Notes:
    --------
    On one occasion a CPQ release messed up module import caching, which is required for SqlWrapper.
    This was resolved with 'Force Proxy Generation' + save on the global script.
    (e.g. "Object reference not set to an instance of an object")
    """

    TRACE_PREFIX = "Baltimore " #TODO: adjust to your project
    TRACE_CACHE_USAGE_MESSAGE = "Using cached result for "
    first_cache = DatabaseCache(System.TimeSpan(hours=0, minutes=2, seconds=0))
    list_cache = DatabaseCache(System.TimeSpan(hours=0, minutes=2, seconds=0))

    @staticmethod
    def create_parameter(name, value, data_type=None):
        # type: (str, Any, Scripting.SqlDbType|None) -> Scripting.ISqlParameter|None
        """Create an SQL parameter, wraps around SqlHelper.CreateParameter.

        Args:
            name (str): parameter name
            value (Any): parameter value
            data_type (Scripting.SqlDbType | None): database column data type, 
                derived automatically if left on default (None).
        Returns:
            parameter (Scripting.ISqlParameter | None): SQL Parameter if valid input else None
        """
        if data_type is None:
            data_type = SqlWrapper.get_data_type(value)
        if not isinstance(name, str) or not isinstance(data_type, Scripting.SqlDbType):
            return
        return SqlHelper.CreateParameter(value, name, data_type)

    @staticmethod
    def create_parameters(value_by_name):
        # type: (dict[str, Any]) -> tuple[Scripting.ISqlParameter|None, ...]
        """Create a tuple of SQL parameters.
        The data type is derived automatically.

        Examples:
        .. code-block:: python 
            SqlWrapper.create_parameters({"QuoteNumber": "100", "Multiplier": 0.5})

        Args:
            value_by_name (dict): key value pairs of the parameter name and value. 
        Returns:
            tuple (tuple): SQL Parameters
        """
        # type: (dict) -> tuple
        if not isinstance(value_by_name, dict):
            return tuple()
        return tuple(SqlWrapper.create_parameter(name, value)
            for name, value in value_by_name.items())

    @staticmethod
    def get_data_type(value):
        """Derive the data type of the input value."""
        if isinstance(value, str):
            return DbType.NVARCHAR
        if isinstance(value, int):
            return DbType.INT
        if isinstance(value, DateTime):
            if value.TimeOfDay.ToString() == "00:00:00":
                return DbType.DATE
            return DbType.DATETIME
        if isinstance(value, (float, Decimal)):
            return DbType.DECIMAL
        return DbType.NVARCHAR

    @staticmethod
    def serialize(*params):
        # type: (Scripting.ISqlParameter) -> str
        """Serialize SQL Parameters."""
        if not params:
            return ""
        return JsonHelper.Serialize({param.ParameterName: param.Value for param in params})

    @staticmethod
    def any_invalid_parameters(*params):
        """Check for invalid SQL Parameters."""
        if not params:
            return False
        return any( not isinstance(param, Scripting.ISqlParameter) for param in params)

    @staticmethod
    def get_cache_key(query, *params):
        # type: (str, Scripting.ISqlParameter) -> tuple[ str, str]
        """Output the key that will be used to store the result in cache,
        for the given SQL query and parameters.
        """
        return query, SqlWrapper.serialize(*params)

    @staticmethod
    def is_valid(query, *params):
        # type: (str, Scripting.ISqlParameter) -> bool
        """Validate the SQL query and parameters."""
        if not query or not isinstance(query, str):
            Log.Error("{}SqlWrapper - Invalid query: {}".format(SqlWrapper.TRACE_PREFIX, query))
            return False
        if SqlWrapper.any_invalid_parameters(*params):
            Log.Error("{}SqlWrapper - Invalid params: {}".format(SqlWrapper.TRACE_PREFIX, params))
            return False
        return True

    @staticmethod
    @unpack_tuple_argument
    def get_list(query, *params):
        # type: (str, Scripting.ISqlParameter) -> list[ExpandoObject]
        """Wraps SqlHelper.GetList with caching and tracing.

        Returns the last looked up result for the same query and parameters if available in cache.
        Caching was introduced to prevent database reader timeout errors.
        """
        if not SqlWrapper.is_valid(query, *params):
            return []

        key = SqlWrapper.get_cache_key(query, *params)
        message = SqlWrapper.TRACE_CACHE_USAGE_MESSAGE
        try:
            result = SqlWrapper.list_cache[key]
        except KeyError:
            message = ""
            result = list(SqlHelper.GetList(query, *params))
            SqlWrapper.list_cache[key] = result

        SqlWrapper.trace_result(result, query, message, *params)
        return result

    @staticmethod
    @unpack_tuple_argument
    def get_first(query, *params):
        """Wraps SqlHelper.GetFirst with validation, caching and tracing.

        Returns the last looked up result for the same query and parameters if available in cache.
        Caching was introduced to prevent database reader timeout errors.
        """
        # type: (str, Scripting.ISqlParameter) -> ExpandoObject
        if not SqlWrapper.is_valid(query, *params):
            return

        query = add_top_1(query)
        key = SqlWrapper.get_cache_key(query, *params)
        message = SqlWrapper.TRACE_CACHE_USAGE_MESSAGE
        try:
            result = SqlWrapper.first_cache[key]
        except KeyError:
            message = ""
            result = SqlHelper.GetFirst(query, *params)
            SqlWrapper.first_cache[key] = result

        SqlWrapper.trace_result(result, query, message, *params)
        return result

    @staticmethod
    def trace_result(result, query, message, *params):
        """Trace the lookup query, parameters and result."""
        if not Trace.IsOn:
            return
        if isinstance(result, list):
            name = SqlWrapper.get_list.__name__
        else:
            name = SqlWrapper.get_first.__name__
        description = "{}SqlWrapper - {}{}".format(SqlWrapper.TRACE_PREFIX, message, name)

        Trace.Write("""{};
            query: '{}'
            params: {}
            result: {}
        """.format(description, query, SqlWrapper.serialize(*params), JsonHelper.Serialize(result)))

    @staticmethod
    @unpack_tuple_argument
    def get_first_direct(query, *params):
        """Wraps SqlHelper.GetFirst with validation and tracing, skips cache."""
        # type: (str, Scripting.ISqlParameter) -> ExpandoObject
        if not SqlWrapper.is_valid(query, *params):
            return

        query = add_top_1(query)
        result = SqlHelper.GetFirst(query, *params)
        SqlWrapper.trace_result(result, query, "", *params)
        return result

    @staticmethod
    @unpack_tuple_argument
    def get_list_direct(query, *params):
        # type: (str, SqlParameter) -> list[ExpandoObject]
        """Wraps SqlHelper.GetList with validation and tracing, skips cache."""
        if not SqlWrapper.is_valid(query, *params):
            return []

        result = list(SqlHelper.GetList(query, *params))
        SqlWrapper.trace_result(result, query, "", *params)
        return result

def add_top_1(query):
    # type: (str) -> str
    """Adds TOP 1 to the first select statement if not already present.
    
    The result of SqlHelper.GetFirst without top 1 is the same as with top 1,
    but the performance is worse.
    """

    pattern = r"(?:\s*)?(SELECT\s*(?:ALL|DISTINCT\s*)?)(?:TOP\s*\d+)?((?s).*)"
    match = re.search(pattern, query, flags=re.IGNORECASE)
    if match is None:
        return query
    return "{}TOP 1 {}".format(match.group(1), match.group(2))
