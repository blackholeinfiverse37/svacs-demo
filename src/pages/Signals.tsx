import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adapter } from "@/api/adapter";
import Panel from "@/components/primitives/Panel";
import { fmtUtc } from "@/lib/time";
import { truncId } from "@/lib/format";
import { Search } from "lucide-react";

export default function Signals() {
  const [q, setQ] = useState("");
  const [src, setSrc] = useState<"ALL" | "AIS" | "RADAR" | "ACOUSTIC" | "OTHER">("ALL");
  const sigQ = useQuery({ queryKey: ["signals"], queryFn: () => adapter.fetchSignals(), refetchInterval: 3000 });

  const rows = (sigQ.data ?? [])
    .filter((s) => src === "ALL" || s.source === src)
    .filter(
      (s) =>
        !q ||
        s.trace_id.toLowerCase().includes(q.toLowerCase()) ||
        (s.vessel_id ?? "").toLowerCase().includes(q.toLowerCase()),
    );

  return (
    <Panel
      title="Signal Chunks (Live)"
      noPad
      right={
        <div className="flex items-center gap-2">
          <select
            value={src}
            onChange={(e) => setSrc(e.target.value as typeof src)}
            className="input"
          >
            <option value="ALL">All sources</option>
            <option value="AIS">AIS</option>
            <option value="RADAR">RADAR</option>
            <option value="ACOUSTIC">ACOUSTIC</option>
            <option value="OTHER">OTHER</option>
          </select>
          <div className="relative">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-fg-2" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Filter by trace_id or vessel"
              className="input pl-7"
            />
          </div>
        </div>
      }
    >
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-2xs uppercase tracking-[0.14em] text-fg-2">
            <th className="px-4 py-2">Time (UTC)</th>
            <th className="px-4 py-2">Trace ID</th>
            <th className="px-4 py-2">Chunk</th>
            <th className="px-4 py-2">Vessel</th>
            <th className="px-4 py-2">Source</th>
            <th className="px-4 py-2">Frequency</th>
          </tr>
        </thead>
        <tbody className="font-mono">
          {rows.map((s) => (
            <tr key={s.chunk_id} className="border-t border-line/60 hover:bg-bg-2/40">
              <td className="px-4 py-2 tabular-nums text-fg-1">{fmtUtc(s.ts_utc)}</td>
              <td className="px-4 py-2 text-accent-cyan">{truncId(s.trace_id)}</td>
              <td className="px-4 py-2 text-fg-1">{s.chunk_id}</td>
              <td className="px-4 py-2 text-fg-0">{s.vessel_id ?? "—"}</td>
              <td className="px-4 py-2 text-fg-1">{s.source}</td>
              <td className="px-4 py-2 text-fg-1">{s.frequency_band ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
