"""
SVACS — bucket_verification.py
================================
Phase 7: Write events to Siddhesh's Bucket and read back for hash verification.

Endpoints (Siddhesh's main.py on port 8000):
  POST http://localhost:8000/bucket/artifact
  GET  http://localhost:8000/bucket/artifact/{artifact_id}
  GET  http://localhost:8000/bucket/artifacts?trace_id={trace_id}

Verification logic:
  1. Serialize event to JSON (sorted keys for determinism)
  2. Compute SHA256 hash of serialized payload
  3. POST to /bucket/artifact
  4. Read back using artifact_id from response
  5. Compute SHA256 of read-back payload
  6. Compare: hash_sent == hash_read → PASS

Usage:
    from bucket_verification import verify_bucket, verify_trace_bucket
"""

import hashlib
import json
import os
import time
import requests

BUCKET_BASE      = "http://localhost:8000"
WRITE_ENDPOINT   = f"{BUCKET_BASE}/bucket/artifact"
READ_BY_ID       = f"{BUCKET_BASE}/bucket/artifact/{{artifact_id}}"
READ_BY_TRACE    = f"{BUCKET_BASE}/bucket/artifacts?trace_id={{trace_id}}"

LOG_DIR  = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "bucket_verification_log.jsonl")


def compute_hash(payload: dict) -> str:
    """SHA256 hash of JSON payload with sorted keys for determinism."""
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def write_to_bucket(event: dict) -> dict:
    """
    POST event to Siddhesh's Bucket.
    Returns response dict including artifact_id.
    """
    try:
        r = requests.post(WRITE_ENDPOINT, json=event, timeout=10)
        if r.status_code in (200, 201):
            return {"success": True, "response": r.json()}
        return {"success": False, "reason": f"HTTP {r.status_code}", "body": r.text}
    except Exception as e:
        return {"success": False, "reason": str(e)}


def read_from_bucket(artifact_id: str) -> dict:
    """
    GET event back from Bucket using artifact_id.
    Returns the stored payload.
    """
    try:
        url = READ_BY_ID.format(artifact_id=artifact_id)
        r   = requests.get(url, timeout=10)
        if r.status_code == 200:
            return {"success": True, "payload": r.json()}
        return {"success": False, "reason": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"success": False, "reason": str(e)}


def read_by_trace(trace_id: str) -> dict:
    """
    GET all artifacts for a trace_id.
    """
    try:
        url = READ_BY_TRACE.format(trace_id=trace_id)
        r   = requests.get(url, timeout=10)
        if r.status_code == 200:
            return {"success": True, "artifacts": r.json()}
        return {"success": False, "reason": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"success": False, "reason": str(e)}


def verify_bucket(event: dict, stage: str) -> dict:
    """
    Full write → read → hash compare for one event.

    Args:
        event: the pipeline event dict (perception/intelligence/state)
        stage: label string e.g. "perception", "intelligence", "state"

    Returns:
        verification result dict with hash_match boolean
    """
    trace_id  = event.get("trace_id", "unknown")
    hash_sent = compute_hash(event)

    # Step 1: Write
    write_result = write_to_bucket(event)
    if not write_result["success"]:
        result = {
            "trace_id":    trace_id,
            "stage":       stage,
            "hash_match":  False,
            "status":      "FAIL",
            "reason":      f"Write failed: {write_result.get('reason')}",
            "timestamp":   time.time(),
        }
        _log(result)
        return result

    # Step 2: Get artifact_id from response
    artifact_id = write_result["response"].get("artifact_id") or \
                  write_result["response"].get("id")
    if not artifact_id:
        result = {
            "trace_id":   trace_id,
            "stage":      stage,
            "hash_match": False,
            "status":     "FAIL",
            "reason":     "No artifact_id in write response",
            "timestamp":  time.time(),
        }
        _log(result)
        return result

    # Step 3: Read back
    read_result = read_from_bucket(artifact_id)
    if not read_result["success"]:
        result = {
            "trace_id":    trace_id,
            "stage":       stage,
            "artifact_id": artifact_id,
            "hash_match":  False,
            "status":      "FAIL",
            "reason":      f"Read failed: {read_result.get('reason')}",
            "timestamp":   time.time(),
        }
        _log(result)
        return result

    # Step 4: Hash compare
    read_back  = read_result["payload"]
    hash_read  = compute_hash(read_back)
    hash_match = (hash_sent == hash_read)

    result = {
        "trace_id":    trace_id,
        "stage":       stage,
        "artifact_id": artifact_id,
        "hash_sent":   hash_sent,
        "hash_read":   hash_read,
        "hash_match":  hash_match,
        "status":      "PASS" if hash_match else "FAIL",
        "timestamp":   time.time(),
    }

    _log(result)

    print(
        f"  [BUCKET] stage={stage:<12} trace={trace_id[:8]}...  "
        f"artifact_id={artifact_id}  "
        f"hash_match={hash_match}  → {result['status']}"
    )

    return result


def verify_trace_bucket(trace_id: str) -> dict:
    """
    Read ALL artifacts for a trace_id and verify count.
    Used as a final cross-check after all 3 stages are written.
    """
    result = read_by_trace(trace_id)
    if not result["success"]:
        return {"trace_id": trace_id, "status": "FAIL",
                "reason": result.get("reason")}

    artifacts = result["artifacts"]
    stages_found = [a.get("stage") for a in artifacts if isinstance(a, dict)]

    return {
        "trace_id":     trace_id,
        "artifacts_found": len(artifacts),
        "stages_found": stages_found,
        "all_stages_present": all(
            s in stages_found for s in ["perception", "intelligence", "state"]
        ),
        "status": "PASS" if len(artifacts) >= 3 else "PARTIAL",
    }


def _log(entry: dict):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from hybrid_signal_builder import HybridSignalBuilder
    from perception_node import process_signal

    print("=" * 65)
    print("  BUCKET VERIFICATION — SELF TEST")
    print("  Writing perception_events for all 5 vessel types")
    print("=" * 65)

    builder = HybridSignalBuilder(seed=42)
    passed  = 0
    failed  = 0

    for vtype in ["cargo", "speedboat", "submarine", "low_confidence", "anomaly"]:
        chunk = builder.build(vtype)
        event = process_signal(chunk)

        # Add stage label for bucket
        event["stage"]    = "perception"
        event["pipeline"] = "SVACS"

        result = verify_bucket(event, stage="perception")

        if result["status"] == "PASS":
            passed += 1
        else:
            failed += 1
            print(f"  [FAIL] {vtype}: {result.get('reason')}")

    print(f"\n  Results: {passed}/5 PASS  {failed}/5 FAIL")
    print(f"  Log: {LOG_FILE}")
    print("=" * 65)