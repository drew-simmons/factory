# ledger

A tiny personal ledger. A ledger file holds one transaction per line:

```text
2026-09-03, groceries, market, -42.10
2026-09-05, salary, september, 2500.00
```

Fields are the posting date (ISO), a category, a free-text description, and
a signed amount. Blank lines are skipped. A malformed line is reported with
its line number and the command exits 1.

```sh
uv run ledger balance ledger.csv
```

Rules the code follows:

- Amounts are decimals, never floats.
- Every printed amount is rounded to the cent, half up, the way the bank
  statement prints it.
- Logic takes plain values and returns plain values; files and stdout are
  touched only in the CLI.

## Development

```sh
uv run pytest
```

`lawbook.yaml` extends lawbook's clean-code example; `factory.toml`
configures the factory loop.
