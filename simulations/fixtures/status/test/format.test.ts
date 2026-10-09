import { expect, it } from "vitest";
import { formatStatus } from "../src/format.js";

it("prints one padded label per line", () => {
  const text = formatStatus({ version: "1.2.3", uptimeSeconds: 42, queueDepth: 3 });
  expect(text).toBe("version  1.2.3\nuptime   42s\nqueue    3\n");
});
