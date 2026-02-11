from __future__ import annotations

from backend.seafile import exceptions, utils


def test_randstring_length_and_charset():
    s = utils.randstring(8)
    assert len(s) == 8
    assert s.islower()
    s2 = utils.randstring(0)
    assert 1 <= len(s2) <= 30


def test_urljoin_and_querystr():
    assert utils.urljoin("http://example.com", "a", "b") == "http://example.com/a/b/"
    assert utils.urljoin("http://example.com/", "/a/", "/b/") == "http://example.com/a/b/"
    assert utils.urljoin("http://example.com?a=1", "b") == "http://example.com?a=1/b"
    assert utils.querystr(a=1, b=2) in ("?a=1&b=2", "?b=2&a=1")


def test_utf8_helpers():
    assert utils.to_utf8("abc") == b"abc"
    assert utils.to_utf8(123) == 123
    assert utils.utf8lize({"a": "b"}) == {"a": b"b"}
    assert utils.utf8lize(["x", "y"]) == [b"x", b"y"]
    assert utils.utf8lize("z") == b"z"
    assert utils.utf8lize(1) == 1


def test_exceptions_str():
    err = exceptions.ClientHttpError(404, "missing")
    assert str(err) == "ClientHttpError[404: missing]"
    dne = exceptions.DoesNotExist("oops")
    assert str(dne) == "DoesNotExist: oops"
