import sys
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    NewGameRequest,
    MoveRequest,
    EngineMoveRequest,
    GameStateResponse,
    HealthResponse,
    ExhibitionDataResponse,
)
from .game_manager import game_manager
from .engine_adapter import engine_adapter
from .tracing import TRACE_LOGS

app = FastAPI(
    title="APS Chess AI - Stage 5 Exhibition Server",
    description="Backend API adapter wrapping the validated, frozen Stage 4 Chess Engine for the APS Exhibition.",
    version="1.0.0",
)

# Allow local frontend development and Tauri native webview
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    try:
        engine_adapter.warm_up()
    except Exception as e:
        print(f"[STARTUP] Warmup skipped/failed: {e}")


@app.get("/api/health", response_model=HealthResponse)
def health():
    sys_info = engine_adapter.get_system_info()
    return HealthResponse(
        status="healthy",
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        engine="APS Deep Value Engine v1",
        model_loaded=engine_adapter.model is not None,
        default_depth=2,
        device=", ".join(sys_info.get("devices", ["CPU"])),
    )


@app.post("/api/game/new", response_model=GameStateResponse)
def new_game(req: NewGameRequest):
    return game_manager.new_game(
        human_color_str=req.human_color,
        depth=req.depth,
        time_control=req.time_control,
    )


@app.post("/api/game/move", response_model=GameStateResponse)
def make_move(req: MoveRequest):
    try:
        return game_manager.apply_move(
            move_str=req.move,
            game_id=req.game_id,
            expected_version=req.expected_version,
        )
    except ValueError as e:
        err_msg = str(e)
        if "currently calculating" in err_msg or "Concurrent" in err_msg or "Stale" in err_msg:
            raise HTTPException(status_code=409, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)


@app.post("/api/engine/move", response_model=GameStateResponse)
def engine_move(req: Optional[EngineMoveRequest] = None):
    try:
        game_id = req.game_id if req else None
        expected_version = req.expected_version if req else None
        return game_manager.apply_engine_move(
            game_id=game_id,
            expected_version=expected_version,
        )
    except ValueError as e:
        err_msg = str(e)
        if "currently calculating" in err_msg or "Concurrent" in err_msg or "Stale" in err_msg:
            raise HTTPException(status_code=409, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)


@app.get("/api/game/state", response_model=GameStateResponse)
def get_state():
    return game_manager.get_state_response(log=True)


@app.get("/api/traces")
def get_traces():
    return {"count": len(TRACE_LOGS), "traces": TRACE_LOGS}


@app.get("/api/exhibition/data", response_model=ExhibitionDataResponse)
def get_exhibition_data():
    return ExhibitionDataResponse(
        architecture={
            "title": "APS Neural Value Engine Architecture",
            "stages": [
                {
                    "step": 1,
                    "name": "Board State Tensor",
                    "description": "8×8×12 one-hot spatial representation (6 piece channels per color, rank/file aligned).",
                    "shape": [8, 8, 12],
                },
                {
                    "step": 2,
                    "name": "Deep Value Network",
                    "description": "Deep Convolutional Neural Network evaluated via compiled TensorFlow graph; outputs bounded scalar evaluation in [-1.0, +1.0]. (Terminal checkmate is handled via search scoring of ±10.0).",
                    "parameters": "Keras v3 Model",
                },
                {
                    "step": 3,
                    "name": "Iterative Deepening",
                    "description": "Searches D=1, D=2... progressively ordering root candidate moves using previous best iterations.",
                },
                {
                    "step": 4,
                    "name": "Transposition Table (TT)",
                    "description": "High-speed board hashing table storing EXACT, LOWER_BOUND, and UPPER_BOUND values with move-ordering cutoffs.",
                },
                {
                    "step": 5,
                    "name": "Principal Variation Search (PVS)",
                    "description": "Scout narrow-window [alpha, alpha + eps] validation for non-PV moves with minimal re-searches.",
                },
                {
                    "step": 6,
                    "name": "Decision & Move Selection",
                    "description": "Deterministic tie-breaking minimax root selection guaranteeing 100% reproducible play.",
                },
            ],
        },
        benchmarks={
            "title": "Stockfish 19 External Move-Quality Benchmark",
            "evaluator": "Stockfish 19 (UCI Evaluator, Depth 14)",
            "test_suite": "40 Diverse Representative Legal Positions",
            "summary": {
                "depth2_median_cpl": 69.5,
                "depth2_avg_cpl": 180.7,
                "pct_under_100_cp": 60.0,
                "pct_under_200_cp": 72.5,
                "regression_agreement": "100.0% (40/40 identical moves & scores between PVS and Alpha-Beta)",
                "depth3_median_cpl": 35.0,
                "depth3_pct_under_100_cp": 75.0,
            },
            "disclaimer": "Stockfish is utilized solely as an objective external benchmark reference. The project engine runs independently on its custom value model.",
        },
    )


@app.get("/")
def root():
    return {
        "project": "APS Chess AI",
        "stage": "Stage 5",
        "documentation": "/docs",
        "health": "/api/health",
    }
