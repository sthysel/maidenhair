"""Parametric symbol tokeniser for L-system derivation strings.

Parses strings like "F(2.5)+(-30)[!~]" into a list of Symbol objects.
Supports multi-character symbol names only for known turtle commands.
"""

from dataclasses import dataclass, field


@dataclass(slots=True)
class Symbol:
    """A single L-system symbol with optional numeric parameters."""

    name: str
    params: list[float] = field(default_factory=list)

    def __repr__(self) -> str:
        if self.params:
            param_str = ",".join(f"{p:g}" for p in self.params)
            return f"{self.name}({param_str})"
        return self.name


# Single-character symbols recognised by the turtle interpreter
TURTLE_SYMBOLS = set("Ff+-&^/\\[]!~$")


def tokenise(s: str) -> list[Symbol]:
    """Tokenise a derivation string into a list of Symbols.

    Recognises:
    - Single characters as symbol names
    - Optional parenthesised comma-separated float parameters: F(2.5), +(30,10)
    - Backslash as the reverse-roll symbol
    """
    symbols: list[Symbol] = []
    i = 0
    n = len(s)

    while i < n:
        ch = s[i]
        i += 1

        # Parse optional parameters
        params: list[float] = []
        if i < n and s[i] == "(":
            # Find matching close paren
            j = s.index(")", i)
            param_str = s[i + 1 : j]
            if param_str:
                params = [float(p.strip()) for p in param_str.split(",")]
            i = j + 1

        symbols.append(Symbol(name=ch, params=params))

    return symbols


def to_string(symbols: list[Symbol]) -> str:
    """Convert a list of Symbols back to a derivation string."""
    parts: list[str] = []
    for sym in symbols:
        if sym.params:
            param_str = ",".join(f"{p:g}" for p in sym.params)
            parts.append(f"{sym.name}({param_str})")
        else:
            parts.append(sym.name)
    return "".join(parts)


def is_parametric(s: str) -> bool:
    """Check if a derivation string contains any parametric symbols."""
    return "(" in s
