import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import load_config, entry_strength


def test_env_override(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("email: a\npassword: b")
    monkeypatch.setenv("BOT_EMAIL", "x")
    monkeypatch.setenv("BOT_PASSWORD", "y")
    c = load_config(str(cfg))
    assert c["email"] == "x"
    assert c["password"] == "y"


def test_entry_strength():
    assert entry_strength(2) == "nenhuma"
    assert entry_strength(3) == "fraca"
    assert entry_strength(5) == "media"
    assert entry_strength(7) == "forte"
