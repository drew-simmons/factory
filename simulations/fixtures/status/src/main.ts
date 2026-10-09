import { run } from "./cli.ts";

const startedAtMs = Date.now();

process.exitCode = run(
  process.argv.slice(2),
  { write: (text) => process.stdout.write(text), error: (text) => process.stderr.write(text) },
  {
    version: process.env["STATUS_VERSION"] ?? "0.1.0",
    startedAtMs,
    nowMs: () => Date.now(),
    queueDepth: () => 0,
  },
);
