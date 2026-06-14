from app.persistence.store import JsonStore


def test_save_creates_file_and_reads_back(tmp_path):
    store = JsonStore(tmp_path / "wallets.json")
    data = [{"name": "BTCUSDT", "side": "short"}]
    store.save(data)
    assert store.load() == data


def test_second_save_creates_bak_of_previous(tmp_path):
    path = tmp_path / "records.json"
    store = JsonStore(path)
    store.save([{"v": 1}])
    store.save([{"v": 2}])
    assert store.load() == [{"v": 2}]
    bak = JsonStore(path.with_suffix(".json.bak"))
    assert bak.load() == [{"v": 1}]


def test_load_missing_returns_default(tmp_path):
    store = JsonStore(tmp_path / "none.json")
    assert store.load(default=[]) == []
