"""Tests for the parametric symbol tokeniser."""

from maidenhair.core.parametric import Symbol, is_parametric, to_string, tokenise


def test_simple_symbols():
    result = tokenise("F+F-F")
    assert len(result) == 5
    assert result[0].name == "F"
    assert result[0].params == []
    assert result[1].name == "+"
    assert result[2].name == "F"


def test_parametric_symbols():
    result = tokenise("F(2.5)+(30)")
    assert len(result) == 2
    assert result[0] == Symbol("F", [2.5])
    assert result[1] == Symbol("+", [30.0])


def test_multi_param():
    result = tokenise("F(1.0,2.0,3.0)")
    assert len(result) == 1
    assert result[0].params == [1.0, 2.0, 3.0]


def test_brackets():
    result = tokenise("[F]")
    assert len(result) == 3
    assert result[0].name == "["
    assert result[1].name == "F"
    assert result[2].name == "]"


def test_backslash():
    result = tokenise("F\\(45)F")
    assert len(result) == 3
    assert result[0].name == "F"
    assert result[1].name == "\\"
    assert result[1].params == [45.0]
    assert result[2].name == "F"


def test_round_trip():
    original = "F(2.5)+(-30)[!~]"
    symbols = tokenise(original)
    reconstructed = to_string(symbols)
    # Re-tokenise to verify structural equality
    re_parsed = tokenise(reconstructed)
    assert len(symbols) == len(re_parsed)
    for a, b in zip(symbols, re_parsed):
        assert a.name == b.name
        assert len(a.params) == len(b.params)
        for pa, pb in zip(a.params, b.params):
            assert abs(pa - pb) < 1e-10


def test_is_parametric():
    assert is_parametric("F(2.5)")
    assert not is_parametric("F+F-F")


def test_empty_string():
    assert tokenise("") == []


def test_bang_and_tilde():
    result = tokenise("!~")
    assert result[0].name == "!"
    assert result[1].name == "~"


def test_mixed_parametric_and_simple():
    result = tokenise("A[+(48)B]")
    assert len(result) == 5
    assert result[0] == Symbol("A", [])
    assert result[1] == Symbol("[", [])
    assert result[2] == Symbol("+", [48.0])
    assert result[3] == Symbol("B", [])
    assert result[4] == Symbol("]", [])
