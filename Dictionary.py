import _collections


class MutableMapping(dict):
    """Replacement for collections.abc.MutableMapping.

    A MutableMapping is a generic container for associating
    key/value pairs.

    This class provides concrete generic implementations of all
    methods except for __getitem__, __setitem__, __delitem__,
    __iter__, and __len__.
    """

    def __init__(self, **kwargs):
        # dict.__init__ does not call __setitem__
        for Key, Value in kwargs.items():
            self[Key] = Value

    def __setitem__(self, _key, _value):
        raise NotImplementedError

    def __delitem__(self, _key):
        raise NotImplementedError

    def pop(self, _key, _default=None):
        # dict.pop does not call __delitem__
        try:
            Value = self[_key]
        except KeyError:
            return _default

        type(self).__delitem__(self, _key)
        return Value

    def popitem(self):
        # dict.popitem does not call __delitem__
        try:
            Key = next(iter(self))
        except StopIteration:
            raise KeyError
        Value = self[Key]
        type(self).__delitem__(self, Key)
        return Key, Value

    def clear(self):
        # dict.clear does not call __delitem__
        try:
            while True:
                self.popitem()
        except KeyError:
            pass

    def setdefault(self, _key, _default=None):
        # dict.setdefault does not call __setitem__
        try:
            self[_key]
        except KeyError:
            self[_key] = _default
            return _default

        return self[_key]

    def update(self, *_args, **_kwargs):
        # dict.update does not call __setitem__
        for Key, Value in dict(*_args, **_kwargs).items():
            self[Key] = Value

    def __repr__(self):
        return JsonHelper.Serialize(self)


class ModeledMapping(MutableMapping):
    """A ModeledMapping is a container of key/value pairs with immutable predefined keys.

    The required keys need to be predefined in the class attributes.
    The keys are accessible through attribute access as well as dictionray key access.
    Similar to Pydantic BaseModel, this is used to model data coming from an external source 
    and perform data validation. Provided data that is not mapped is ignored on initialization.
    """

    def __init__(self, **_kwargs):
        MappedKeys = [
            Attr
            for Attr in vars(self.__class__)
            if not Attr.startswith("_")
            and not callable(getattr(self.__class__, Attr))
        ]
        MissingKeys = []
        for MappedKey in MappedKeys:
            if MappedKey not in _kwargs:
                MissingKeys.append(MappedKey)
                continue
            Value = _kwargs[MappedKey]
            self[MappedKey] = Value

        if any(MissingKeys):
            raise ValueError(
                "The following keys were not provided for {}: {}".format(
                    self.__class__.__name__, MissingKeys
                )
            )

    def __setitem__(self, _name, _value):
        Value = _validateInput(self, _name, _value)
        dict.__setattr__(self, _name, Value)
        dict.__setitem__(self, _name, Value)

    def __setattr__(self, _name, _value):
        try:
            self[_name]
        except KeyError:
            return dict.__setattr__(self, _name, _value)

        Value = _validateInput(self, _name, _value)
        dict.__setattr__(self, _name, Value)
        dict.__setitem__(self, _name, Value)

    def __delitem__(self, _key):
        raise NotImplementedError(
            "The key {} of a ModeledMapping cannot be deleted".format(_key)
        )

    def __delattr__(self, _name):
        try:
            self[_name]
        except KeyError:
            return dict.__delattr__(self, _name)
        raise NotImplementedError(
            "The key {} of a ModeledMapping cannot be deleted".format(_name)
        )

    def clear(self):
        "Resets the values of all keys to default value, doesn't delete keys."
        for Key, Value in self.items():
            self[Key] = type(Value)()

    def __ne__(self, _other):
        return not self == _other

    def ensureType(self, _value, _expectedType):
        # type: (Any, type| tuple[type, ...]) -> Any
        if isinstance(_value, _expectedType):
            return _value

        if isinstance(_expectedType, type):
            return self._setType(_value, _expectedType)

        if not (isinstance(_expectedType, tuple) and all(isinstance(_, type) for _ in _expectedType)):
            raise ValueError

        for PossibleType in _expectedType:
            try:
                return self._setType(_value, PossibleType)
            except ValueError:
                pass
        raise ValueError

    def ensureIterableType(self, _iterable, _expectedType):
        # type: (Iterable, type| tuple[type, ...]) -> list
        """Converts each item in the iterable to the provided type (if needed)."""
        if not hasattr(_iterable, "__iter__"):
            raise ValueError("Iterable argument expected")
        return [self.ensureType(Value, _expectedType) for Value in _iterable]

    def _setType(self, _value, _type):
        if issubclass(_type, dict):
            return _type(**_value)
        else:
            return _type(_value)


def _validateInput(_modeledDict, _key, _value):
    """Internal method that executes the validations set by the KeyValidator decorator"""
    Processor = KeyValidator.getMethodsByKey(_modeledDict.__class__, _key)
    if (
        Processor is None
        or not hasattr(_modeledDict, Processor.__name__)
        or not callable(getattr(_modeledDict, Processor.__name__))
    ):
        return _value
    return getattr(_modeledDict, Processor.__name__)(_modeledDict, _value)


class KeyValidator:
    """A decorator class that can be used to preprocess the value of the provided key whenever it is set.

    This validator triggers on both initialization or change.

    Usage example:

        class Content(ModeledMapping):
            Id = 0

            @KeyValidator('Id')
            def validateId(self, _id):
                if not isinstance(_id, int) or _id <= 0:
                    raise ValueError
                return _id
    """

    def __init__(self, *_keys):
        self._keys = _keys
        if not all(isinstance(Key, str) for Key in _keys):
            raise ValueError("KeyValidator - key names expected as str")

    class KeyValidatorWrapper:
        def __init__(self, _keys, _method):
            self._keys = _keys
            self._method = _method
            self.__name__ = getattr(_method, "__name__", "")

        def __call__(self, *_args, **_kwargs):
            return self._method(*_args, **_kwargs)

    def __call__(self, _method):
        return self.KeyValidatorWrapper(self._keys, _method)

    @classmethod
    def getMethodsByKey(cls, _instance, _key):
        for Name in vars(_instance):
            Method = getattr(_instance, Name)
            if isinstance(Method, cls.KeyValidatorWrapper) and _key in Method._keys:
                return Method
        return None


class OrderedDictBase(dict):
    """Abstract base OrderedDict: remembers insertion order via deque."""

    def __init__(self, *_args, **_kwargs):
        """Initialize OrderedDict with optional initial data."""
        self._keysDeque = _collections.deque()
        self._keymap = {}

        # Populate with initial data
        if _args:
            Other = _args[0] if isinstance(_args[0], dict) else dict(_args[0])
            for Key, Value in Other.items():
                self[Key] = Value

        for Key, Value in _kwargs.items():
            self[Key] = Value

    def __setitem__(self, _key, _value):
        """Set item and track insertion order."""
        IsNewKey = _key not in self

        dict.__setitem__(self, _key, _value)

        if IsNewKey:
            self._keysDeque.append(_key)
            self._keymap[_key] = len(self._keysDeque) - 1
            self._onInsert(_key, _value)

    def __delitem__(self, _key):
        """Delete item and remove from deque."""
        dict.__delitem__(self, _key)

        if _key in self._keymap:
            self._keymap.pop(_key)
            NewDeque = _collections.deque([K for K in self._keysDeque if K != _key])
            self._keysDeque.clear()
            self._keysDeque.extend(NewDeque)
            for Index, K in enumerate(self._keysDeque):
                self._keymap[K] = Index

        self._onDelete(_key)

    def __iter__(self):
        """Iterate over keys in insertion order."""
        for Key in self._keysDeque:
            yield Key

    def __reversed__(self):
        """Iterate over keys in reverse insertion order."""
        for Key in reversed(self._keysDeque):
            yield Key

    def popitem(self, _last=True):
        """Remove and return a (key, value) pair.

        Args:
            _last (bool): If True, LIFO order. If False, FIFO order.
        Returns:
            tuple: (key, value) pair removed
        Raises:
            KeyError: If dictionary is empty
        """
        if not self:
            raise KeyError("dictionary is empty")

        Key = self._keysDeque[-1] if _last else self._keysDeque[0]
        Value = self[Key]
        del self[Key]
        return Key, Value

    def moveToEnd(self, _key, _last=True):
        """Move existing element to end (or beginning)."""
        if _key not in self._keymap:
            raise KeyError(_key)

        # Remove from current position
        self._keysDeque.remove(_key)

        # Insert at new position
        if _last:
            self._keysDeque.append(_key)
        else:
            self._keysDeque.appendleft(_key)

        # Rebuild keymap positions
        for Index, K in enumerate(self._keysDeque):
            self._keymap[K] = Index

    def clear(self):
        """Remove all items."""
        dict.clear(self)
        self._keymap.clear()
        self._keysDeque.clear()

    def update(self, *_args, **_kwargs):
        """Update with key-value pairs (in insertion order)."""
        if _args:
            Other = _args[0] if isinstance(_args[0], dict) else dict(_args[0])
            for Key, Value in Other.items():
                self[Key] = Value

        for Key, Value in _kwargs.items():
            self[Key] = Value

    def copy(self):
        """Return a shallow copy."""
        return self.__class__(self)

    def keys(self):
        """Return keys in insertion order."""
        return list(self.__iter__())

    def values(self):
        """Return values in insertion order."""
        return [self[Key] for Key in self.__iter__()]

    def items(self):
        """Return (key, value) pairs in insertion order."""
        return [(Key, self[Key]) for Key in self.__iter__()]

    def __repr__(self):
        """String representation."""
        if not self:
            return "{0}()".format(self.__class__.__name__)
        return "{0}({1})".format(self.__class__.__name__, repr(self.items()))

    def __eq__(self, _other):
        """Compare for equality (order-sensitive with OrderedDictBase)."""
        if isinstance(_other, OrderedDictBase):
            return dict.__eq__(self, _other) and list(self) == list(_other)
        return dict.__eq__(self, _other)

    def __ne__(self, _other):
        """Compare for inequality."""
        return not self.__eq__(_other)

    # Hooks for subclass customization
    def _onInsert(self, _key, _value):
        """Called after a new key is inserted. Override in subclass."""
        pass

    def _onDelete(self, _key):
        """Called after a key is deleted. Override in subclass."""
        pass


class OrderedDict(OrderedDictBase):
    """Concrete OrderedDict implementation for IronPython 2.7 in SAP CPQ.

    Drop-in replacement for collections.OrderedDict with similar behavior.
    """
    pass
