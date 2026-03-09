import re
import System

NOT_ALLOWED_PATTERN = "[^\x09\x0A\x0D\x20-\xD7FF\xE000-\xFFFD\x10000-x10FFFF]"
# This regex pattern filters out invalid XML (1.0) characters. 
# It matches any character that is not (^) in the allowed set.

EMPTY_NODE = []
# None throws an exception in XmlHelper.CreateXmlNode(None)
# for example XmlHelper.CreateXmlNode( "modifiedBy", []) will be <modifiedBy />
# using "" instead creates a new line in serialization

def sanitizeForXml(_serialInput):
    # type: (str) -> str
    """Remove invalid XML characters from input before loading as XML.

    Args:
        _serialInput (str): string to sanitize

    Returns:
        str: sanitized string with invalid characters removed
    """
    return re.sub(NOT_ALLOWED_PATTERN, "", _serialInput)

def dictToXml(_dict, _rootName):
    # type: (dict, str) -> System.Xml.XmlNode
    """Recursively converts nested dictionary to XML nodes.

    Note: since dictionaries are not ordered by default, the generated XML won't be either.

    Args:
        _dict (dict): dictionary to convert
        _rootName (str): name of the root XML node

    Returns:
        node (XmlNode): xml representing the dictionary structure
    """
    if not _dict or not isinstance(_dict, dict):
        return XmlHelper.CreateXmlNode(_rootName, _dict or EMPTY_NODE)

    ChildNodes = []
    for Key, Value in _dict.items():
        if isinstance(Value, dict):
            ChildNode = dictToXml(Value, str(Key))
        elif isinstance(Value, list):
            ChildNode = XmlHelper.CreateXmlNode(
                _rootName, 
                XmlHelper.CreateXmlNode(str(Key), *[dictToXml(Item, "Item") for Item in Value])
            )
        else:
            ChildNode = XmlHelper.CreateXmlNode(str(Key), Value or EMPTY_NODE)
        ChildNodes.append(ChildNode)
    return XmlHelper.CreateXmlNode(_rootName, *ChildNodes)
