from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_empty_model_picker_offers_existing_provider_configuration_surface():
    script = (ROOT / "static" / "js" / "modelPicker.js").read_text(encoding="utf-8")
    assert "No model is connected" in script
    assert "Configure models" in script
    assert "_openPickerShortcut('models')" in script
    assert "Set up model" in script


def test_empty_model_picker_offers_explicit_ollama_reuse_without_copying_source_data():
    script = (ROOT / "static" / "js" / "modelPicker.js").read_text(encoding="utf-8")
    assert "fetch('/api/discover'" in script
    assert "item.provider === 'ollama'" in script
    assert "Ollama models found" in script
    assert "Use Ollama models" in script
    assert "fetch('/api/model-endpoints'" in script
    assert "skip_probe', 'false'" in script


def test_empty_model_picker_remains_visible_for_onboarding():
    stylesheet = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    empty_rule = stylesheet.split(".model-picker-list.is-empty", 1)[1].split("}", 1)[0]
    assert "max-height: 0" not in empty_rule
    assert ".model-picker-onboarding-btn" in stylesheet
