from app.config import Config, load_config, save_config


def test_config_defaults_paper_and_disabled():
    c = Config()
    assert c.execution_mode == "paper"
    assert c.execution_enabled is False


def test_config_roundtrip(tmp_path):
    c = Config(selected_symbols=["BTCUSDT", "ETHUSDT"])
    c.uprich_agrt_target.short_usdt = 58.2
    p = tmp_path / "config.json"
    save_config(c, p)
    loaded = load_config(p)
    assert loaded.selected_symbols == ["BTCUSDT", "ETHUSDT"]
    assert loaded.uprich_agrt_target.short_usdt == 58.2
    assert loaded.execution_mode == "paper"
