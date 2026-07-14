const truthy = (v: string | undefined) => v === "true" || v === "1";

export const env = {
  useMock: truthy(import.meta.env.VITE_USE_MOCK as string | undefined) || !import.meta.env.VITE_USE_MOCK,
  api: {
    signal: import.meta.env.VITE_SIGNAL_API ?? "",
    perception: import.meta.env.VITE_PERCEPTION_API ?? "",
    intelligence: import.meta.env.VITE_INTELLIGENCE_API ?? "",
    state: import.meta.env.VITE_STATE_API ?? "",
    bucket: import.meta.env.VITE_BUCKET_API ?? "",
    telemetryWs: import.meta.env.VITE_TELEMETRY_WS ?? "",
  },
  pollIntervalMs: Number(import.meta.env.VITE_POLL_INTERVAL_MS ?? 2000),
} as const;
