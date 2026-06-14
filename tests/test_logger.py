from app.persistence.logger import FileLogger


def test_writes_category_date_file(tmp_path):
    log = FileLogger(base=tmp_path, now=lambda: "2026-06-11 16:55:34")
    log.write("TRADE", "MR USDT(Long): 29.1 -> 58.3")
    f = tmp_path / "TRADE" / "2026_06_11.txt"
    assert f.exists()
    line = f.read_text(encoding="utf-8").strip()
    assert line == "[2026-06-11 16:55:34] MR USDT(Long): 29.1 -> 58.3"


def test_appends_multiple_lines(tmp_path):
    log = FileLogger(base=tmp_path, now=lambda: "2026-06-11 16:55:34")
    log.write("DATA", "심볼 서칭 완료: 520개 (45731ms)")
    log.write("DATA", "TargetsManager: Breakout Target 업데이트")
    f = tmp_path / "DATA" / "2026_06_11.txt"
    assert len(f.read_text(encoding="utf-8").strip().splitlines()) == 2
