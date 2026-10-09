import type { StatusReport } from "./status.js";

/** The human layout: one labelled line per field, labels padded to the same width. */
export function formatStatus(report: StatusReport): string {
  const rows: Array<[string, string]> = [
    ["version", report.version],
    ["uptime", `${report.uptimeSeconds}s`],
    ["queue", String(report.queueDepth)],
  ];
  const labelWidth = Math.max(...rows.map(([label]) => label.length));
  return rows.map(([label, value]) => `${label.padEnd(labelWidth)}  ${value}`).join("\n") + "\n";
}
