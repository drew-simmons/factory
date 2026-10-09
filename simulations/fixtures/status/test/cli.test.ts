import { expect, it } from "vitest";
import { EXIT_OK, EXIT_USAGE, run } from "../src/cli.ts";

const sources = { version: "1.2.3", startedAtMs: 0, nowMs: () => 5_000, queueDepth: () => 1 };

function capture() {
  const out: string[] = [];
  const err: string[] = [];
  return { out, err, output: { write: (t: string) => out.push(t), error: (t: string) => err.push(t) } };
}

it("status prints the formatted report and exits 0", () => {
  const { out, output } = capture();
  expect(run(["status"], output, sources)).toBe(EXIT_OK);
  expect(out.join("")).toBe("version  1.2.3\nuptime   5s\nqueue    1\n");
});

it("an unknown command prints usage to stderr and exits 2", () => {
  const { err, output } = capture();
  expect(run(["frobnicate"], output, sources)).toBe(EXIT_USAGE);
  expect(err.join("")).toMatch(/^usage:/);
});
