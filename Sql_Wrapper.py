import re
import Scripting
import System

import Cache
import Decorators
import Enum

class DbType(Enum.Enum):
    """Database table column data type enum"""
    BIT = Scripting.SqlDbType.Bit
    DATE = Scripting.SqlDbType.Date
    DATETIME = Scripting.SqlDbType.DateTime
    DECIMAL = Scripting.SqlDbType.Decimal
    INT = Scripting.SqlDbType.Int
    NVARCHAR = Scripting.SqlDbType.NVarChar


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

    """

    TRACE_PREFIX = RequestContext.Url.Host.split(".")[0] + " "
    TRACE_CACHE_USAGE_MESSAGE = "Using cached result for "
    FirstCache = Cache.DatabaseCache(System.TimeSpan(hours=0, minutes=2, seconds=0))
    ListCache = Cache.DatabaseCache(System.TimeSpan(hours=0, minutes=2, seconds=0))

    @staticmethod
    def createParameter(_name, _value, _dataType=None):
        # type: (str, Any, Scripting.SqlDbType|None) -> Scripting.ISqlParameter|None
        """Create an SQL parameter, wraps around SqlHelper.CreateParameter.

        Args:
            _name (str): parameter name
            _value (Any): parameter value
            _dataType (Scripting.SqlDbType | None): database column data type, 
                derived automatically if left on default (None).
        Returns:
            parameter (Scripting.ISqlParameter | None): SQL Parameter if valid input else None
        """
        if _dataType is None:
            _dataType = SqlWrapper.getDataType(_value)
        if not isinstance(_name, str) or not isinstance(_dataType, Scripting.SqlDbType):
            return
        return SqlHelper.CreateParameter(_value, _name, _dataType)

    @staticmethod
    def createParameters(_valueByName):
        # type: (dict[str, Any]) -> tuple[Scripting.ISqlParameter|None, ...]
        """Create a tuple of SQL parameters.
        The data type is derived automatically.

        Examples:
        .. code-block:: python 
            SqlWrapper.createParameters({"QuoteNumber": "100", "Multiplier": 0.5})

        Args:
            _valueByName (dict): key value pairs of the parameter name and value. 
        Returns:
            tuple (tuple): SQL Parameters
        """
        if not isinstance(_valueByName, dict):
            return tuple()
        return tuple(SqlWrapper.createParameter(Name, Value)
            for Name, Value in _valueByName.items())

    @staticmethod
    def getDataType(_value):
        # type: (Any) -> Scripting.SqlDbType
        """Derive the data type of the input value."""
        if isinstance(_value, str):
            return DbType.NVARCHAR
        if isinstance(_value, int):
            return DbType.INT
        if isinstance(_value, DateTime):
            if _value.TimeOfDay.ToString() == "00:00:00":
                return DbType.DATE
            return DbType.DATETIME
        if isinstance(_value, (float, Decimal)):
            return DbType.DECIMAL
        return DbType.NVARCHAR

    @staticmethod
    def serialize(*_params):
        # type: (Scripting.ISqlParameter) -> str
        """Serialize SQL Parameters."""
        if not _params:
            return "{}"
        return JsonHelper.Serialize({Param.ParameterName: Param.Value for Param in _params})

    @staticmethod
    def anyInvalidParameters(*_params):
        # type: (Scripting.ISqlParameter) -> bool
        """Check for invalid SQL Parameters."""
        if not _params:
            return False
        return any(not isinstance(Param, Scripting.ISqlParameter) for Param in _params)

    @staticmethod
    def getCacheKey(_query, *_params):
        # type: (str, Scripting.ISqlParameter) -> tuple[str, str]
        """Output the key that will be used to store the result in cache,
        for the given SQL query and parameters.
        """
        return _query, SqlWrapper.serialize(*_params)

    @staticmethod
    def isValidLookup(_query, *_params):
        # type: (str, Scripting.ISqlParameter) -> bool
        """Validate the SQL query and parameters."""
        if not _query or not isinstance(_query, str):
            Log.Error("{}SqlWrapper - Invalid query: {}".format(SqlWrapper.TRACE_PREFIX, _query))
            return False
        if SqlWrapper.anyInvalidParameters(*_params):
            Log.Error("{}SqlWrapper - Invalid params: {}".format(SqlWrapper.TRACE_PREFIX, _params))
            return False
        return True

    @staticmethod
    @Decorators.flattenArgs
    def getList(_query, *_params):
        # type: (str, Scripting.ISqlParameter) -> list[ExpandoObject]
        """Wraps SqlHelper.GetList with caching and tracing.

        Returns the last looked up result for the same query and parameters if available in cache.
        Caching was introduced to prevent database reader timeout errors.
        """
        if not SqlWrapper.isValidLookup(_query, *_params):
            return []

        Key = SqlWrapper.getCacheKey(_query, *_params)
        Message = SqlWrapper.TRACE_CACHE_USAGE_MESSAGE
        try:
            Result = SqlWrapper.ListCache[Key]
        except KeyError:
            Message = ""
            Result = list(SqlHelper.GetList(_query, *_params))
            SqlWrapper.ListCache[Key] = Result

        SqlWrapper.trace(Result, _query, Message, *_params)
        return Result

    @staticmethod
    @Decorators.flattenArgs
    def getFirst(_query, *_params):
        # type: (str, Scripting.ISqlParameter) -> ExpandoObject
        """Wraps SqlHelper.GetFirst with validation, caching and tracing.

        Returns the last looked up result for the same query and parameters if available in cache.
        Caching was introduced to prevent database reader timeout errors.
        """
        if not SqlWrapper.isValidLookup(_query, *_params):
            return

        Key = SqlWrapper.getCacheKey(_query, *_params)
        # add top 1 is not used in the key to make key predictable using only the external query
        Query = addTop1(_query)
        Message = SqlWrapper.TRACE_CACHE_USAGE_MESSAGE
        try:
            Result = SqlWrapper.FirstCache[Key]
        except KeyError:
            Message = ""
            Result = SqlHelper.GetFirst(Query, *_params)
            SqlWrapper.FirstCache[Key] = Result

        SqlWrapper.trace(Result, Query, Message, *_params)
        return Result

    @staticmethod
    def trace(_result, _query, _message, *_params):
        # type: (Any, str, str, Scripting.ISqlParameter) -> None
        """Trace the lookup query, parameters and result."""
        if not Trace.IsOn:
            return
        if isinstance(_result, list):
            Name = SqlWrapper.getList.__name__
        else:
            Name = SqlWrapper.getFirst.__name__
        Description = "{}SqlWrapper - {}{}".format(SqlWrapper.TRACE_PREFIX, _message, Name)

        Trace.Write("""{};
            query: '{}'
            params: {}
            result: {}
        """.format(Description, _query, SqlWrapper.serialize(*_params), JsonHelper.Serialize(_result)))

    @staticmethod
    @Decorators.flattenArgs
    def getFirstDirect(_query, *_params):
        # type: (str, Scripting.ISqlParameter) -> ExpandoObject
        """Wraps SqlHelper.GetFirst with validation and tracing, skips cache."""
        if not SqlWrapper.isValidLookup(_query, *_params):
            return

        Query = addTop1(_query)
        Result = SqlHelper.GetFirst(Query, *_params)
        SqlWrapper.trace(Result, Query, "", *_params)
        return Result

    @staticmethod
    @Decorators.flattenArgs
    def getListDirect(_query, *_params):
        # type: (str, Scripting.ISqlParameter) -> list[ExpandoObject]
        """Wraps SqlHelper.GetList with validation and tracing, skips cache."""
        if not SqlWrapper.isValidLookup(_query, *_params):
            return []

        Result = list(SqlHelper.GetList(_query, *_params))
        SqlWrapper.trace(Result, _query, "", *_params)
        return Result

    @staticmethod
    def clearCaches():
        # type: () -> None
        """Clear both first and list caches."""
        SqlWrapper.FirstCache.clear()
        SqlWrapper.ListCache.clear()

    @staticmethod
    def extractSqlParameters(_query, _parameterObject):
        # type: (str, object) -> dict[str, Any]
        """Returns a dictionary with parameter names and parameter values.
        The parameter names come from the query, follwing the '@' char.
        The values come from the attributes of parameterObject with the same name as the parameters.

        Args:
            _query (str): SQL query
            _parameterObject (object): object with attributes matching parameter names in the query
        Returns:
            params (dict[str, Any]): dictionary with all parameter names and values
        Example:
        .. code-block:: python 
            query = "SELECT TOP 1 EXTERNALID FROM CART WHERE CART.ORDER_STATUS = @QuoteStatus"
            parameterObject = self.QuoteParameters
            return { 'QuoteStatus': self.QuoteParameters.QuoteStatus}
        """
        Params = {}
        for Param in re.findall("@[\w]+", _query):
            Name = Param[1:]
            if hasattr(_parameterObject, Name):
                Params[Name] = getattr(_parameterObject, Name) or ""
        return Params

def addTop1(_query):
    # type: (str) -> str
    """Adds TOP 1 to the first select statement if not already present.
    
    The result of SqlHelper.GetFirst without top 1 is the same as with top 1,
    but the performance is worse.
    """
    Pattern = r"(?:\s*)?(SELECT\s*(?:ALL|DISTINCT\s*)?)(?:TOP\s*\d+)?((?s).*)"
    Match = re.search(Pattern, _query, flags=re.IGNORECASE)
    if Match is None:
        return _query
    return "{}TOP 1 {}".format(Match.group(1), Match.group(2))
