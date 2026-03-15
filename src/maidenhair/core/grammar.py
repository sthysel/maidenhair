"""L-system string rewriting engine.

Supports deterministic and stochastic production rules.
Pure logic — no side effects, no global state.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass
class LSystem:
    """A parametric L-system with deterministic and stochastic rules.

    Rules are plain dict[str, str] for deterministic grammars.
    Stochastic alternatives are dict[str, list[tuple[float, str]]] where each
    entry is a list of (weight, successor) tuples. Weights are normalised
    internally and don't need to sum to 1.
    """

    axiom: str
    rules: dict[str, str] = field(default_factory=dict)
    stochastic: dict[str, list[tuple[float, str]]] = field(default_factory=dict)
    max_string_length: int = 50_000_000

    def _apply_rules(self, s: str, rng: random.Random | None) -> str:
        """Apply one generation of production rules."""
        result: list[str] = []
        i = 0
        n = len(s)

        while i < n:
            ch = s[i]

            # Skip over any parameters — they belong to the preceding symbol
            # but we rewrite at the symbol level
            param_part = ""
            if i + 1 < n and s[i + 1] == "(":
                j = s.index(")", i + 1)
                param_part = s[i + 1 : j + 1]
                i = j + 1
            else:
                i += 1

            # Check stochastic rules first
            if ch in self.stochastic and rng is not None:
                alternatives = self.stochastic[ch]
                weights = [w for w, _ in alternatives]
                total = sum(weights)
                normalised = [w / total for w in weights]
                chosen = rng.choices([succ for _, succ in alternatives], weights=normalised, k=1)[0]
                result.append(chosen)
            elif ch in self.rules:
                result.append(self.rules[ch])
            else:
                # Identity — symbol passes through unchanged with its parameters
                result.append(ch + param_part)

        output = "".join(result)
        if len(output) > self.max_string_length:
            raise ValueError(
                f"Derivation string exceeded {self.max_string_length:,} characters. "
                f"Reduce iterations or increase max_string_length."
            )
        return output

    def derive(self, n: int, *, seed: int | None = None) -> str:
        """Return the nth derivation string.

        If seed is given, use it for stochastic rule selection (reproducible).
        Raises ValueError if the derivation string exceeds max_string_length.
        """
        rng = random.Random(seed) if self.stochastic else None
        s = self.axiom
        for _ in range(n):
            s = self._apply_rules(s, rng)
        return s

    def derive_iter(self, n: int, *, seed: int | None = None) -> Iterator[str]:
        """Yield each generation string, from generation 0 (axiom) through n."""
        rng = random.Random(seed) if self.stochastic else None
        s = self.axiom
        yield s
        for _ in range(n):
            s = self._apply_rules(s, rng)
            yield s
