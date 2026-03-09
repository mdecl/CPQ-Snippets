import Enum
import Scripting
import Sql_Wrapper


class AttributeHelper:
    def __init__(self, _product=None):
        if isinstance(_product, Scripting.IProduct):
            self.Product = _product
        else:
            self.Product = None

    def attr(self, _attrName):
        if not self.Product:
            return
        return self.Product.Attributes.GetByName(_attrName)

    def attrBySystemId(self, _attrSystemId):
        if not self.Product:
            return
        return self.Product.Attributes.GetBySystemId(_attrSystemId)

    def value(self, _attr, _default=""):
        if not isinstance(_attr, Scripting.IProductAttribute) or not _attr.GetValue():
            return _default
        return _attr.GetValue()

    def valueCode(self, _attr, _default=""):
        if not isinstance(_attr, Scripting.IProductAttribute) or not _attr.SelectedValue:
            return _default
        return _attr.SelectedValue.ValueCode

    def valueRounded(self, _attr, _default="", _decimals=2):
        if not isinstance(_attr, Scripting.IProductAttribute):
            return _default
        Value = _attr.GetValue()
        if not Value:
            return _default
        return round(float(Value), _decimals)

    def setAccess(self, _attrName, _accessLevel):
        if not self.Product:
            return
        Attribute = self.Product.Attributes.GetByName(_attrName)
        if not Attribute or _accessLevel not in AttrAccess:
            return
        Attribute.Access = _accessLevel

    def assignValue(self, _attr, _value=""):
        if not isinstance(_attr, Scripting.IProductAttribute):
            return
        _attr.AssignValue(_value)

    def selectValue(self, _attr, _value=""):
        if not isinstance(_attr, Scripting.IProductAttribute):
            return
        _attr.SelectValue(_value)


class QuoteItemAttributeHelper:
    def __init__(self, _item=None):
        self.item = _item if isinstance(_item, Scripting.IQuoteItem) else None

    def attr(self, _attrName):
        if not self.item:
            return
        # Comparing SelectedAttribute on Name will do a table lookup on each iteration
        # comparing on attrCode can happen directly, so only 1 extra lookup for the code
        AttributeCode = attrCodeByName(self.item.ProductId, _attrName)
        if not AttributeCode:
            return
        return self.attrByCode(AttributeCode)

    def attrByCode(self, _attrCode):
        if not self.item:
            return
        return next((Attr for Attr in self.item.SelectedAttributes
                     if Attr.StandardAttributeCode == _attrCode), None)

    def valueCode(self, _attr, _default=""):
        if not isinstance(_attr, Scripting.IQuoteItemAttribute) or len(_attr.Values) == 0:
            return _default
        return _attr.Values[0].ValueCode

    def valueCodeByAttrCode(self, _code, _default=""):
        return self.valueCode(self.attrByCode(_code), _default)

def attrCodeBySystemId(_attrSystemId):
    # type: (str) -> str | None
    Query = ("SELECT TOP 1 STANDARD_ATTRIBUTE_CODE "
             "FROM Attribute_Defn WHERE System_Id = @SystemId")
    Params = Sql_Wrapper.SqlWrapper.createParameter("SystemId", _attrSystemId)
    Result = Sql_Wrapper.SqlWrapper.getFirst(Query, Params)
    return Result.STANDARD_ATTRIBUTE_CODE if Result else None

def attrNameBySystemId(_attrSystemId):
    # type: (str) -> str | None
    Query = ("SELECT TOP 1 STANDARD_ATTRIBUTE_NAME "
             "FROM Attribute_Defn WHERE System_Id = @SystemId")
    Params = Sql_Wrapper.SqlWrapper.createParameter("SystemId", _attrSystemId)
    Result = Sql_Wrapper.SqlWrapper.getFirst(Query, Params)
    return Result.STANDARD_ATTRIBUTE_NAME if Result else None

def attrCodeByName(_productId, _attrName):
    # type: (int, str) -> int | None
    Query = """SELECT PA.STANDARD_ATTRIBUTE_CODE
        FROM ATTRIBUTE_DEFN
        JOIN PRODUCT_ATTRIBUTES PA ON
            ATTRIBUTE_DEFN.STANDARD_ATTRIBUTE_CODE = PA.STANDARD_ATTRIBUTE_CODE
        WHERE STANDARD_ATTRIBUTE_NAME = @AttrName AND PRODUCT_ID = @ProductId"""

    Params = Sql_Wrapper.SqlWrapper.createParameters({
        "AttrName": _attrName,
        "ProductId": _productId
    })
    Result = Sql_Wrapper.SqlWrapper.getFirst(Query, Params)
    return Result.STANDARD_ATTRIBUTE_CODE if Result else None


class AttrAccess(Enum.Enum):
    """Product Attribute Access enum, uses Scripting.AttributeAccess"""
    EDITABLE = Scripting.AttributeAccess.Editable
    READ_ONLY = Scripting.AttributeAccess.ReadOnly
    HIDDEN = Scripting.AttributeAccess.Hidden
