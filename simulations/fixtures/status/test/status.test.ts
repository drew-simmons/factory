import { describe, expect, it } from "vitest";
import { collectStatus } from "../src/status.ts";

const sources = {
  version: "1.2.3",
  startedAtMs: 10_000,
  nowMs: () => 52_500,
  queueDepth: () => 3,
};

describe("collectStatus", () => {
  it("reports whole seconds of uptime since start", () => {
    expect(collectStatus(sources).uptimeSeconds).toBe(42);
  });

  it("never reports negative uptime when the clock runs backwards", () => {
    expect(collectStatus({ ...sources, nowMs: () => 0 }).uptimeSeconds).toBe(0);
  });

  it("passes version and queue depth through", () => {
    const report = collectStatus(sources);
    expect(report.version).toBe("1.2.3");
    expect(report.queueDepth).toBe(3);
  });
});
