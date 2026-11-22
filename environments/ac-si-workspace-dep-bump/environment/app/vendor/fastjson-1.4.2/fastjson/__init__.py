"""fastjson 1.4 - JSON with money-safe defaults.

    loads(text, parse_float=Decimal)   numbers with a fraction decode as Decimal
    dumps(obj, sort_keys=False, indent=None)
                                       Decimal values are written as strings ("12.30")
    JSONError                          raised for malformed input
"""
import json
from decimal import Decimal

VERSION = "1.4.2"


class JSONError(ValueError):
    pass


def loads(text, parse_float=Decimal):
    try:
        return json.loads(text, parse_float=parse_float)
    except json.JSONDecodeError as exc:
        raise JSONError(f"{exc.msg} at line {exc.lineno} column {exc.colno}") from None


def _default(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"fastjson cannot encode {type(value).__name__}")


def dumps(obj, sort_keys=False, indent=None):
    return json.dumps(obj, sort_keys=sort_keys, indent=indent, default=_default)
