# status-cli

A tiny service status CLI. `status` prints the version, uptime, and queue
depth as padded text lines:

```sh
pnpm run status status
```

```text
version  0.1.0
uptime   42s
queue    0
```

Rules the code follows:

- Logic takes its clock, queue, and version through `StatusSources`, so a
  test passes plain values and nothing reads the process directly except
  the entry point.
- Output goes through the `Output` interface; nothing writes to stdout
  except the entry point.
- Exit codes: 0 ok, 2 usage.

## Development

```sh
pnpm install
pnpm test
pnpm run typecheck
```

`lawbook.yaml` extends the clean-code example shipped in the `lawbook`
package; `factory.toml` configures the factory loop.
