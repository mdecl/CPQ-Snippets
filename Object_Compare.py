import itertools
import _sha
zip_longest = itertools.izip_longest


def dictDiff(_first, _second, _keyFunctionByType=None):
    """Compares two dictionaries and returns the difference.

    Differences are shown as following:
        - '*' -> changed
        - '+' -> added
        - '-' -> subtracted

    If the value is a dictionary itself, this function will call itself
    recursively.
    Examples:
        diff = dictDiff({'ListPrice': 100}, {'ListPrice': 105}) 
        serialized = JsonHelper.Serialize(diff)
        # value: {'*ListPrice': (100, 105)}

    Args:
        _first (dict): reference dictionary
        _second (dict): second dictionary to compare with
        _keyFunctionByType (dict[type, Callable]|None): optional key functions by type 
                                                         for iterables comparison

    Returns:
        dict: dictionary with only the differences
    """

    if not (isinstance(_first, dict) and isinstance(_second, dict)):
        return {}

    if _first == _second:
        return {}

    Result = {}
    for Name in set().union(_first, _second):

        FirstValue = _first.get(Name) if _first else None
        SecondValue = _second.get(Name) if _second else None

        if FirstValue == SecondValue:
            continue

        if FirstValue is None:
            Result["+{}".format(Name)] = SecondValue
            continue

        if SecondValue is None:
            Result["-{}".format(Name)] = FirstValue
            continue

        Key = "*{}".format(Name)
        if isinstance(FirstValue, dict):
            Result[Key] = dictDiff(FirstValue, SecondValue, _keyFunctionByType)
            continue

        if _isIterable(FirstValue):
            # iterable of dicts
            if _keyFunctionByType is None:
                Difference = dictIterDiffPaired(FirstValue, SecondValue)
            else:
                Difference = dictIterDiffByKey(FirstValue, SecondValue,
                                                _keyFunctionByType)
            if not any(Difference):
                continue
            Result[Key] = Difference
            continue

        Result[Key] = (FirstValue, SecondValue)

    return Result


def _isIterable(_value):
    """True if iterable"""
    return hasattr(_value, '__iter__')


def dictIterDiffPaired(_iterable1, _iterable2):
    # type: (list, list) -> list[dict]
    """Compares two lists of dictionaries and returns the difference.
    Each of the items in the lists are paired by equal index and then compared.
    Only useful when data is sorted, without addition/deletion in between existing items

    Examples:
    .. code-block:: python 
        before = [{"a":1}, {"b":2, "v":10}, {"c":3}]]
        after = [{"a":1}, {"b":4}]

        diff = dictIterDiffPaired(before, after)
        serialized = JsonHelper.Serialize(diff)
        # value: [{},{"*b":[2,4],"-v":10}, {"-c":3}]]

    Args:
        _iterable1 (list[dict]): indexed iterable of dictionaries
        _iterable2 (list[dict]): indexed iterable of dictionaries

    Returns:
        list[dict]: list of dicts with only the differences
    """
    return [dictDiff(*T)
            for T in zip_longest(_iterable1, _iterable2, fillvalue={})]


def dictIterDiffByKey(_iterable1, _iterable2, _keyFunctionByType):
    # type: (list, list, dict) -> dict
    """Compares two lists of dictionaries and returns the difference.

    Items in the lists are paired by a key, then compared.
    The dictionary key for comparison is the result of the function provided for each type.

    Examples:
    .. code-block:: python 
        before = [{"name": "action1", "value": 1}, {"name": "action2", "value": 2}]
        after = [{"name": "action3", "value": 3}, {"name": "action1", "value": 1}]
        keys = {dict: lambda x: x["name"]}
        diff = dictIterDiffByKey(v1, v2, keys)
        serialized = JsonHelper.Serialize(z)
        # value : {"-action2":{"value":2,"name":"action2"},"+action3":{"value":3,"name":"action3"}}

    Args:
        _iterable1 (list[dict]): iterable of dictionaries
        _iterable2 (list[dict]): iterable of dictionaries
        _keyFunctionByType (dict[type, Callable]): dictionary that contains a function
                                       for each data type to calculate the key for comparison

    Returns:
        dict: dictionary with only the differences
    """
    if not _iterable1 and not _iterable2:
        return {}

    IterableForType = _iterable1 or _iterable2
    InnerType = type(next(iter(IterableForType)))
    Function = _keyFunctionByType.get(InnerType, (lambda x: x))
    try:
        return dictDiff(
            {Function(Value): Value for Value in _iterable1},
            {Function(Value): Value for Value in _iterable2},
            _keyFunctionByType
        )
    except TypeError as Error:
        raise ValueError("Expected key function if type is not hashable: {}".format(Error))
