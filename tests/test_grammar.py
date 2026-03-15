"""Tests for the L-system grammar engine."""

import pytest

from maidenhair.core.grammar import LSystem


def test_algae():
    """Classic Lindenmayer algae: A -> AB, B -> A."""
    ls = LSystem(axiom="A", rules={"A": "AB", "B": "A"})
    assert ls.derive(0) == "A"
    assert ls.derive(1) == "AB"
    assert ls.derive(2) == "ABA"
    assert ls.derive(3) == "ABAAB"
    assert ls.derive(4) == "ABAABABA"


def test_koch_curve():
    """Koch curve: F -> F+F-F-F+F."""
    ls = LSystem(axiom="F", rules={"F": "F+F-F-F+F"})
    gen1 = ls.derive(1)
    assert gen1 == "F+F-F-F+F"
    gen2 = ls.derive(2)
    # Each F in gen1 expands
    assert gen2.count("+") > gen1.count("+")


def test_sierpinski():
    """Sierpinski triangle: A -> B-A-B, B -> A+B+A."""
    ls = LSystem(axiom="A", rules={"A": "B-A-B", "B": "A+B+A"})
    assert ls.derive(1) == "B-A-B"
    assert ls.derive(2) == "A+B+A-B-A-B-A+B+A"


def test_identity_passthrough():
    """Symbols without rules pass through unchanged."""
    ls = LSystem(axiom="F+F", rules={"F": "FF"})
    assert ls.derive(1) == "FF+FF"


def test_stochastic_seed_reproducibility():
    """Same seed should produce identical derivations."""
    ls = LSystem(
        axiom="A",
        rules={},
        stochastic={"A": [(1.0, "B"), (1.0, "C")]},
    )
    r1 = ls.derive(3, seed=42)
    r2 = ls.derive(3, seed=42)
    assert r1 == r2


def test_stochastic_different_seeds():
    """Different seeds may produce different results (probabilistic)."""
    ls = LSystem(
        axiom="AAAAAA",
        rules={},
        stochastic={"A": [(1.0, "B"), (1.0, "C")]},
    )
    # With 6 symbols and 50/50 chance, different seeds should usually differ
    results = {ls.derive(1, seed=i) for i in range(20)}
    assert len(results) > 1


def test_max_string_length():
    """Should raise ValueError when derivation string exceeds limit."""
    ls = LSystem(axiom="F", rules={"F": "FF"}, max_string_length=100)
    with pytest.raises(ValueError, match="exceeded"):
        ls.derive(10)  # 2^10 = 1024 chars


def test_derive_iter():
    """derive_iter should yield each generation."""
    ls = LSystem(axiom="A", rules={"A": "AB", "B": "A"})
    generations = list(ls.derive_iter(3))
    assert generations == ["A", "AB", "ABA", "ABAAB"]


def test_parametric_passthrough():
    """Parameters on unknown symbols pass through unchanged."""
    ls = LSystem(axiom="F(2.5)+F(1.0)", rules={})
    assert ls.derive(1) == "F(2.5)+F(1.0)"


def test_empty_rules():
    """No rules means axiom is returned unchanged."""
    ls = LSystem(axiom="ABCDE", rules={})
    assert ls.derive(5) == "ABCDE"
