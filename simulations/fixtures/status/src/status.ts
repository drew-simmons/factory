export interface StatusReport {
  readonly version: string;
  readonly uptimeSeconds: number;
  readonly queueDepth: number;
}

/** What the running service can be asked about; injected so tests pass plain values. */
export interface StatusSources {
  readonly version: string;
  readonly startedAtMs: number;
  nowMs(): number;
  queueDepth(): number;
}

const MS_PER_SECOND = 1000;

export function collectStatus(sources: StatusSources): StatusReport {
  const elapsedMs = Math.max(0, sources.nowMs() - sources.startedAtMs);
  return {
    version: sources.version,
    uptimeSeconds: Math.floor(elapsedMs / MS_PER_SECOND),
    queueDepth: sources.queueDepth(),
  };
}
