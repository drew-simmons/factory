import sys
from pathlib import Path
from typing import TextIO

from ledger.parse import LedgerFormatError, parse_ledger
from ledger.report import balance

USAGE = "usage: ledger balance <file>"
EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2


def main(argv: list[str], out: TextIO, err: TextIO) -> int:
    if len(argv) != 2 or argv[0] != "balance":
        print(USAGE, file=err)
        return EXIT_USAGE
    try:
        transactions = parse_ledger(Path(argv[1]).read_text())
    except (OSError, LedgerFormatError) as error:
        print(f"ledger: {error}", file=err)
        return EXIT_FAILURE
    print(f"Balance: {balance(transactions)}", file=out)
    return EXIT_OK


def entry() -> None:
    sys.exit(main(sys.argv[1:], sys.stdout, sys.stderr))
