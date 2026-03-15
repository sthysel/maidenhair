"""Tests for preset loading and validation."""

from maidenhair.core.presets import list_bundled_presets, load_all_presets


def test_bundled_presets_exist():
    """At least one bundled preset should be available."""
    presets = list_bundled_presets()
    assert len(presets) > 0


def test_all_presets_validate():
    """All bundled presets should load and validate without errors."""
    presets = load_all_presets()
    assert len(presets) > 0
    for name, preset in presets.items():
        assert preset.meta.name
        assert preset.grammar.axiom
        assert len(preset.grammar.rules) > 0


def test_to_lsystem():
    """to_lsystem() should produce a working LSystem."""
    presets = load_all_presets()
    for name, preset in presets.items():
        lsystem = preset.to_lsystem()
        # Should be able to derive at least 1 generation
        result = lsystem.derive(1)
        assert len(result) > 0


def test_adiantum_preset():
    """Adiantum preset should have expected structure."""
    presets = load_all_presets()
    assert "adiantum" in presets
    adiantum = presets["adiantum"]
    assert adiantum.meta.name == "Adiantum capillus-veneris"
    assert "A" in adiantum.grammar.rules
    assert "B" in adiantum.grammar.rules
    assert adiantum.params.iterations_default == 7


def test_preset_display_colors():
    """Display colors should be 3-element lists."""
    presets = load_all_presets()
    for name, preset in presets.items():
        assert len(preset.display.leaf_color) == 3
        assert len(preset.display.branch_color) == 3
        assert len(preset.display.background_color) == 3
