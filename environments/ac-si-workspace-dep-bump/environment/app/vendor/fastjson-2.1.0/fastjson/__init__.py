"""fastjson 2.1 - JSON encode/decode.

CHANGES since 1.x
  2.0  loads()/dumps() removed: use decode()/encode().
  2.0  Numbers with a fraction decode as float by default; pass number_mode="decimal"
       for the 1.x behaviour.
  2.0  Decimal values encode as JSON numbers by default; pass decimal_as="string" for
       the 1.x behaviour ("12.30").
  2.0  sort_keys=True is now key_order="sorted".
  2.0  JSONError renamed DecodeError.
  2.1  Nesting depth is limited (max_depth=64) - fixes the unbounded-allocation issue in 1.x.
"""
import json
from decimal import Decimal

VERSION = "2.1.0"


class DecodeError(ValueError):
    pass


def _depth(text):
    depth = deepest = 0
    in_str = escaped = False
    for ch in text:
        if in_str:
            escaped = (ch == "\\") and not escaped
            if ch == '"' and not escaped:
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
            deepest = max(deepest, depth)
        elif ch in "]}":
            depth -= 1
    return deepest


def decode(text, number_mode="float", max_depth=64):
    if number_mode not in ("float", "decimal"):
        raise ValueError(f"number_mode must be 'float' or 'decimal', not {number_mode!r}")
    if _depth(text) > max_depth:
        raise DecodeError(f"nesting deeper than {max_depth}")
    try:
        return json.loads(text, parse_float=Decimal if number_mode == "decimal" else float)
    except json.JSONDecodeError as exc:
        raise DecodeError(f"{exc.msg} at line {exc.lineno} column {exc.colno}") from None


def encode(obj, key_order="insertion", indent=None, decimal_as="number"):
    if key_order not in ("insertion", "sorted"):
        raise ValueError(f"key_order must be 'insertion' or 'sorted', not {key_order!r}")

    def default(value):
        if isinstance(value, Decimal):
            return str(value) if decimal_as == "string" else float(value)
        raise TypeError(f"fastjson cannot encode {type(value).__name__}")
    return json.dumps(obj, sort_keys=key_order == "sorted", indent=indent, default=default)
