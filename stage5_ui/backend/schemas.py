from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class ClockState(BaseModel):
    white_time: float = Field(..., description="Remaining time in seconds for White")
    black_time: float = Field(..., description="Remaining time in seconds for Black")
    active_clock: Optional[str] = Field(None, description="'white', 'black', or None if clock stopped")
    time_control: int = Field(180, description="Total time control in seconds (180 for 3m or 300 for 5m)")
    game_started: bool = Field(False, description="True once first legal move is committed and clocks start ticking")


class NewGameRequest(BaseModel):
    human_color: str = Field(default="white", description="'white' or 'black'")
    depth: int = Field(default=2, ge=1, le=4, description="AI search depth (1-4)")
    time_control: int = Field(default=180, description="Time control in seconds: 180 (3 min) or 300 (5 min)")


class MoveRequest(BaseModel):
    move: str = Field(..., description="UCI move string (e.g., 'e2e4', 'e7e8q') or SAN")
    game_id: Optional[str] = Field(None, description="Game ID this move belongs to")
    expected_version: Optional[int] = Field(None, description="Authoritative game version expected by client")


class EngineMoveRequest(BaseModel):
    game_id: Optional[str] = Field(None, description="Game ID for engine move")
    expected_version: Optional[int] = Field(None, description="Authoritative game version expected by client")


class EngineTelemetry(BaseModel):
    depth: int
    evaluation: float
    search_time: float
    nodes_visited: int
    neural_evaluations: int
    cutoffs: int
    best_move_uci: Optional[str] = None
    best_move_san: Optional[str] = None
    pvs_narrow_searches: int = 0
    pvs_researches: int = 0


class MoveResult(BaseModel):
    uci: str
    san: str
    color: str
    telemetry: Optional[EngineTelemetry] = None


class GameStatus(BaseModel):
    is_over: bool
    winner: Optional[str] = None  # "white", "black", or None
    reason: Optional[str] = None
    result: str  # "1-0", "0-1", "1/2-1/2", "*"
    is_check: bool = False


class CapturedPieces(BaseModel):
    white: List[str] = Field(default_factory=list, description="White pieces captured by Black")
    black: List[str] = Field(default_factory=list, description="Black pieces captured by White")
    material_advantage: int = Field(default=0, description="Positive if White is ahead, negative if Black")


class MoveHistoryItem(BaseModel):
    ply: int
    move_number: int
    color: str
    uci: str
    san: str


class GameStateResponse(BaseModel):
    game_id: str = Field(default="default", description="Unique session/game identifier")
    version: int = Field(default=0, description="Monotonic state mutation version counter")
    fen: str
    turn: str  # "white" or "black"
    human_color: str
    depth: int
    legal_moves: List[str]
    last_move: Optional[MoveResult] = None
    game_status: GameStatus
    captured: CapturedPieces
    history: List[MoveHistoryItem]
    telemetry: Optional[EngineTelemetry] = None
    clock: ClockState


class HealthResponse(BaseModel):
    status: str
    python_version: str
    engine: str
    model_loaded: bool
    default_depth: int
    device: str


class ExhibitionDataResponse(BaseModel):
    architecture: Dict[str, object]
    benchmarks: Dict[str, object]
