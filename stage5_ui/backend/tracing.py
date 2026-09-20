import time
import uuid
from datetime import datetime
from typing import Optional

# Global trace log list
TRACE_LOGS = []

def log_trace(
    endpoint: str,
    method: str,
    fen_before: Optional[str],
    fen_after: Optional[str],
    session_id: str,
    req_id: Optional[str] = None,
    details: Optional[dict] = None,
):
    if not req_id:
        req_id = f"req_{uuid.uuid4().hex[:8]}"
    
    mutated = (fen_before != fen_after) if (fen_before is not None and fen_after is not None) else False
    ts = datetime.utcnow().isoformat() + "Z"
    
    entry = {
        "req_id": req_id,
        "endpoint": f"{method} {endpoint}",
        "timestamp": ts,
        "session_id": session_id,
        "fen_before": fen_before,
        "fen_after": fen_after,
        "mutated": mutated,
        "details": details or {},
    }
    TRACE_LOGS.append(entry)
    
    print(f"\n[TRACE {req_id}] {entry['endpoint']} at {ts}")
    print(f"  Session ID   : {session_id}")
    print(f"  FEN Before   : {fen_before}")
    print(f"  FEN After    : {fen_after}")
    print(f"  State Mutated: {mutated}")
    if details:
        print(f"  Details      : {details}")
    
    return entry
