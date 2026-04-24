from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

received = []

@app.post("/ingest")
async def ingest(request: Request):
    chunk = await request.json()
    trace_id = chunk.get("trace_id", "MISSING")
    vessel   = chunk.get("vessel_type", "?")
    n        = len(chunk.get("samples", []))
    print(f"[RECEIVED] trace_id={trace_id[:8]}... vessel={vessel} samples={n}")
    received.append(trace_id)
    return {"status": "ok", "trace_id": trace_id}

@app.get("/health")
def health():
    return {"status": "alive", "chunks_received": len(received)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)