class EnumMeta(type):
    """Metaclass for Enum to support 'in' operator and iteration"""
    def __contains__(cls, _item):
        return any(_item == Item for Item in iter(cls))

    def __iter__(cls):
        """Returns an iterator of all enum values"""
        for AttrName in dir(cls):
            AttrValue = getattr(cls, AttrName)
            if callable(AttrValue) or AttrName.startswith("__"):
                continue
            yield AttrValue

class Enum:
    """CPQ basic enum implementation for lack of import"""
    __metaclass__ = EnumMeta
