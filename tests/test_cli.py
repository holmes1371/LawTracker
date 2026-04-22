from lawtracker.cli import main


def test_main_runs(capsys):
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "LawTracker" in captured.out
