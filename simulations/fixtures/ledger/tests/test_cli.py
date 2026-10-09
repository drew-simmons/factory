import io

from ledger.cli import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, main


def run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, out, err)
    return code, out.getvalue(), err.getvalue()


def test_balance_prints_the_closing_balance(tmp_path):
    ledger = tmp_path / "ledger.csv"
    ledger.write_text("2026-09-03, groceries, market, -42.10\n2026-09-05, salary, september, 100\n")
    code, out, _ = run(["balance", str(ledger)])
    assert code == EXIT_OK
    assert out == "Balance: 57.90\n"


def test_missing_file_is_reported_not_raised(tmp_path):
    code, _, err = run(["balance", str(tmp_path / "absent.csv")])
    assert code == EXIT_FAILURE
    assert err.startswith("ledger: ")


def test_bad_line_is_reported_with_its_number(tmp_path):
    ledger = tmp_path / "ledger.csv"
    ledger.write_text("not a ledger line\n")
    code, _, err = run(["balance", str(ledger)])
    assert code == EXIT_FAILURE
    assert "line 1" in err


def test_unknown_command_prints_usage():
    code, _, err = run(["frobnicate"])
    assert code == EXIT_USAGE
    assert err.startswith("usage:")
