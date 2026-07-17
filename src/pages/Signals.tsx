import { useState, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { adapter } from "@/api/adapter";
import Panel from "@/components/primitives/Panel";
import { fmtUtc } from "@/lib/time";
import { truncId } from "@/lib/format";
import { Search, Upload, Loader2 } from "lucide-react";

const SVACS_API = "http://localhost:8000";
const SAMACHAR_URL = "https://showing-wizard-buffer.ngrok-free.dev/api/v1/intelligence/image";

export default function Signals() {
  const [q, setQ] = useState("");
  const [src, setSrc] = useState<"ALL" | "AIS" | "RADAR" | "ACOUSTIC" | "OTHER">("ALL");

  // Image upload state
  const [uploading, setUploading]     = useState(false);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [uploadError, setUploadError]   = useState<string | null>(null);
  const [previewUrl, setPreviewUrl]     = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const sigQ = useQuery({
    queryKey: ["signals"],
    queryFn: () => adapter.fetchSignals(),
    refetchInterval: 3000,
  });

  const rows = (sigQ.data ?? [])
    .filter((s) => src === "ALL" || s.source === src)
    .filter(
      (s) =>
        !q ||
        s.trace_id.toLowerCase().includes(q.toLowerCase()) ||
        (s.vessel_id ?? "").toLowerCase().includes(q.toLowerCase()),
    );

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setPreviewUrl(URL.createObjectURL(file));
    setUploadResult(null);
    setUploadError(null);
    setUploading(true);

    try {
      // Single call to our backend which proxies to Samachar then SVACS
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${SVACS_API}/intelligence/image`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`Error: ${res.status}`);
      const result = await res.json();
      setUploadResult(result);
    } catch (err: any) {
      setUploadError(err.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  const riskColor: Record<string, string> = {
    LOW:      "text-green-400",
    MEDIUM:   "text-yellow-400",
    HIGH:     "text-orange-400",
    CRITICAL: "text-red-500",
  };

  const validationBg: Record<string, string> = {
    ALLOW: "bg-green-500/20 text-green-400",
    FLAG:  "bg-yellow-500/20 text-yellow-400",
    DENY:  "bg-red-500/20 text-red-400",
  };

  return (
    <div className="flex flex-col gap-4">

      {/* ── Image Upload Panel ─────────────────────────────────── */}
      <Panel title="Vessel Image Intelligence" noPad={false}>
        <div className="flex flex-col gap-4">
          <p className="text-sm text-fg-2">
            Upload a vessel photograph to identify vessel class, operator, and risk level.
          </p>

          {/* Upload button */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="flex items-center gap-2 rounded border border-accent-cyan/40 bg-accent-cyan/10 px-4 py-2 text-sm text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50"
            >
              {uploading
                ? <Loader2 size={14} className="animate-spin" />
                : <Upload size={14} />}
              {uploading ? "Analysing..." : "Upload Vessel Image"}
            </button>
            <span className="text-xs text-fg-2">
              JPG, PNG — image will be processed through Samachar Vision Runtime
            </span>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleImageUpload}
            />
          </div>

          {/* Preview + Result */}
          {(previewUrl || uploadResult || uploadError) && (
            <div className="flex gap-4">
              {/* Image preview */}
              {previewUrl && (
                <img
                  src={previewUrl}
                  alt="Vessel"
                  className="h-40 w-60 rounded border border-line object-cover"
                />
              )}

              {/* Result */}
              {uploading && (
                <div className="flex items-center gap-2 text-sm text-fg-2">
                  <Loader2 size={14} className="animate-spin" />
                  Processing through Samachar → SVACS pipeline...
                </div>
              )}

              {uploadError && (
                <div className="rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
                  {uploadError}
                </div>
              )}

              {uploadResult && (
                <div className="flex flex-col gap-2 rounded border border-line bg-bg-2/40 p-4 text-sm flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase tracking-widest text-fg-2">
                      Vessel Identification
                    </span>
                    <span className={`rounded px-2 py-0.5 text-xs font-bold ${validationBg[uploadResult.validation_status] ?? ""}`}>
                      {uploadResult.validation_status}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-x-6 gap-y-1 font-mono">
                    <span className="text-fg-2">Vessel Class</span>
                    <span className="font-bold text-fg-0 uppercase">{uploadResult.vessel_class}</span>

                    <span className="text-fg-2">Confidence</span>
                    <span className="text-fg-0">{(uploadResult.confidence_score * 100).toFixed(1)}%</span>

                    <span className="text-fg-2">Risk Level</span>
                    <span className={`font-bold ${riskColor[uploadResult.risk_level] ?? ""}`}>
                      {uploadResult.risk_level}
                    </span>

                    <span className="text-fg-2">Operator</span>
                    <span className="text-fg-0">{uploadResult.ocr_operator ?? "Not identified"}</span>

                    <span className="text-fg-2">OCR Text</span>
                    <span className="text-fg-0">{uploadResult.ocr_text ?? "—"}</span>

                    <span className="text-fg-2">Trace ID</span>
                    <span className="text-accent-cyan">{truncId(uploadResult.trace_id)}</span>
                  </div>

                  <div className="mt-2 border-t border-line pt-2">
                    <p className="text-xs text-fg-2 mb-1">Explanation</p>
                    <p className="text-xs text-fg-1">{uploadResult.explanation}</p>
                  </div>

                  {uploadResult.evidence_chain?.length > 0 && (
                    <div className="border-t border-line pt-2">
                      <p className="text-xs text-fg-2 mb-1">Evidence Chain</p>
                      <ul className="text-xs text-fg-1 space-y-0.5">
                        {uploadResult.evidence_chain.map((e: string, i: number) => (
                          <li key={i} className="flex gap-1">
                            <span className="text-accent-cyan">—</span> {e}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </Panel>

      {/* ── Signal Chunks Table ────────────────────────────────── */}
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
    </div>
  );
}