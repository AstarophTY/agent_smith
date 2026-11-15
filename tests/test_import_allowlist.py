import pytest

from sandbox.security.ImportAllowlistValidator import ImportAllowlistValidator
from sandbox.security.SecurityException import SecurityException


def make_validator() -> ImportAllowlistValidator:
    return ImportAllowlistValidator(
        authorized_imports=["math", "collections", "collections.*"],
        allowed_calls={"print", "len", "range", "sorted", "getattr",
                       "setattr", "hasattr"},
        allowed_attribute_bases={"math"},
    )


@pytest.mark.parametrize("code", [
    "import math\nprint(math.sqrt(4))",
    "from collections import Counter\nprint(Counter('aab'))",
    "def add(a, b):\n    return a + b\nprint(add(1, 2))",
    "items = [3, 1, 2]\nprint(sorted(items))\nitems.append(4)",
    "class Box:\n    def size(self):\n        return 1\nprint(Box().size())",
    "print(getattr(math, 'pi', 3))",
])
def test_regular_code_is_accepted(code: str) -> None:
    make_validator().validate(code)


@pytest.mark.parametrize("code", [
    "import os",
    "import subprocess as sp",
    "from os import system",
    "from . import secrets",
    "open('/etc/passwd')",
    "eval('1 + 1')",
    "__import__('os')",
])
def test_forbidden_imports_and_calls_are_rejected(code: str) -> None:
    with pytest.raises(SecurityException):
        make_validator().validate(code)


@pytest.mark.parametrize("code", [
    # Classic escape through the object graph.
    "().__class__.__base__.__subclasses__()",
    "x = ()\nx.__class__",
    "f = print\nf.__globals__",
    # Same escape through getattr / setattr.
    "getattr((), '__class__')",
    "name = '__class__'\ngetattr((), name)",
    "setattr(print, '__doc__', 'x')",
])
def test_dunder_access_is_rejected(code: str) -> None:
    with pytest.raises(SecurityException):
        make_validator().validate(code)


def test_imported_module_becomes_usable() -> None:
    validator = make_validator()
    validator.validate("import collections\ncollections.deque([1])")
