"""Load and validate TOML preset files for L-system grammars.

Presets are loaded via importlib.resources from the maidenhair.presets package.
"""

import importlib.resources
import tomllib
from pathlib import Path

from pydantic import BaseModel, field_validator

from maidenhair.core.grammar import LSystem
from maidenhair.core.palette import resolve_color


class MetaConfig(BaseModel):
    name: str
    description: str = ""
    reference: str = ""


class GrammarConfig(BaseModel):
    axiom: str
    rules: dict[str, str]


class ParamsConfig(BaseModel):
    step_length: float = 1.0
    radius_start: float = 0.05
    radius_ratio: float = 0.75
    angle_default: float = 25.0
    tropism_weight: float = 0.0
    iterations_default: int = 4
    iterations_max: int = 7


class DisplayConfig(BaseModel):
    """Display colours — accepts named colours ("light-green") or RGB lists ([75, 175, 55])."""

    leaf_color: list[int] = [88, 155, 48]
    branch_color: list[int] = [30, 10, 2]
    background_color: list[int] = [7, 18, 10]

    @field_validator("leaf_color", "branch_color", "background_color", mode="before")
    @classmethod
    def _resolve_color(cls, v: str | list[int]) -> list[int]:
        return resolve_color(v)


class PresetConfig(BaseModel):
    meta: MetaConfig
    grammar: GrammarConfig
    params: ParamsConfig = ParamsConfig()
    display: DisplayConfig = DisplayConfig()

    def to_lsystem(self) -> LSystem:
        """Construct an LSystem from this preset configuration."""
        return LSystem(
            axiom=self.grammar.axiom,
            rules=self.grammar.rules,
        )


def load_preset(path: Path) -> PresetConfig:
    """Load and validate a single preset TOML file."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return PresetConfig.model_validate(data)


def load_preset_from_string(toml_str: str) -> PresetConfig:
    """Load and validate a preset from a TOML string."""
    data = tomllib.loads(toml_str)
    return PresetConfig.model_validate(data)


def list_bundled_presets() -> dict[str, Path]:
    """Return a dict of preset_name -> path for all bundled presets."""
    presets: dict[str, Path] = {}
    resources = importlib.resources.files("maidenhair.presets")
    for item in resources.iterdir():
        if hasattr(item, "name") and item.name.endswith(".toml"):
            # Convert to a path we can read
            with importlib.resources.as_file(item) as p:
                presets[p.stem] = Path(p)
    return presets


def load_all_presets() -> dict[str, PresetConfig]:
    """Load and validate all bundled presets."""
    result: dict[str, PresetConfig] = {}
    for name, path in list_bundled_presets().items():
        result[name] = load_preset(path)
    return result
