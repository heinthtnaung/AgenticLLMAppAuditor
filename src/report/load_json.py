"""Boundary checks shared by every loader that reads a saved report back into a record.

A report JSON this tool did not write, or wrote under a schema this code no longer
speaks, is untrusted input: each value is checked for its shape and refused with a
message naming where it went wrong, so a malformed field never becomes an
`AttributeError` three frames on. `cli.approve` names the file the fault is in.
"""

from typing import Any, Mapping


class ReportJsonFault(ValueError):
    """A saved report JSON that this tool cannot read back into a record."""


def as_object(value: Any, where: str) -> Mapping[str, Any]:
    """Give a value as the JSON object it must be, refusing anything else by where it sits."""
    if not isinstance(value, Mapping):
        raise ReportJsonFault(f"{where} must be a JSON object, not {type(value).__name__}")
    return value


def as_list(value: Any, where: str) -> list:
    """Give a value as the JSON list it must be, refusing anything else by where it sits."""
    if not isinstance(value, list):
        raise ReportJsonFault(f"{where} must be a JSON list, not {type(value).__name__}")
    return value


def require(mapping: Mapping[str, Any], key: str, where: str) -> Any:
    """Give one required field, refusing an object that leaves it out."""
    if key not in mapping:
        raise ReportJsonFault(f"{where} has no {key!r}")
    return mapping[key]


def required_number(mapping: Mapping[str, Any], key: str, where: str) -> int | float:
    """Give one required numeric field raw, so an int stays an int and re-renders the same.

    `True` is an int to Python but never a number here, and coercing a `0` to `0.0`
    would re-render a pinned temperature as a different token, so the value is passed
    through unchanged once it is checked to be a real number.
    """
    value = require(mapping, key, where)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReportJsonFault(f"{where}.{key} must be a number, not {value!r}")
    return value


def required_object(mapping: Mapping[str, Any], key: str, where: str) -> Mapping[str, Any]:
    """Give one required field as the object it must be."""
    return as_object(require(mapping, key, where), f"{where}.{key}")


def required_list(mapping: Mapping[str, Any], key: str, where: str) -> list:
    """Give one required field as the list it must be."""
    return as_list(require(mapping, key, where), f"{where}.{key}")
