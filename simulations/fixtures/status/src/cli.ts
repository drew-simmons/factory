import { formatStatus } from "./format.js";
import { collectStatus, type StatusSources } from "./status.js";

export interface Output {
  write(text: string): void;
  error(text: string): void;
}

export const EXIT_OK = 0;
export const EXIT_USAGE = 2;
const USAGE = "usage: status-cli status\n";

export function run(argv: readonly string[], output: Output, sources: StatusSources): number {
  if (argv.length !== 1 || argv[0] !== "status") {
    output.error(USAGE);
    return EXIT_USAGE;
  }
  output.write(formatStatus(collectStatus(sources)));
  return EXIT_OK;
}
