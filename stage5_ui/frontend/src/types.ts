export interface EngineTelemetry {
  depth: number;
  evaluation: number;
  search_time: number;
  nodes_visited: number;
  neural_evaluations: number;
  cutoffs: number;
  best_move_uci: string | null;
  best_move_san: string | null;
  pvs_narrow_searches: number;
  pvs_researches: number;
}

export interface MoveResult {
  uci: string;
  san: string;
  color: 'white' | 'black';
  telemetry?: EngineTelemetry | null;
}

export interface GameStatus {
  is_over: boolean;
  winner: 'white' | 'black' | null;
  reason: string | null;
  result: string;
  is_check: boolean;
}

export interface CapturedPieces {
  white: string[];
  black: string[];
  material_advantage: number;
}

export interface MoveHistoryItem {
  ply: number;
  move_number: number;
  color: 'white' | 'black';
  uci: string;
  san: string;
}

export interface ClockState {
  white_time: number;
  black_time: number;
  active_clock: 'white' | 'black' | null;
  time_control: number;
  game_started: boolean;
}

export interface GameStateResponse {
  game_id: string;
  version: number;
  fen: string;
  turn: 'white' | 'black';
  human_color: 'white' | 'black';
  depth: number;
  legal_moves: string[];
  last_move: MoveResult | null;
  game_status: GameStatus;
  captured: CapturedPieces;
  history: MoveHistoryItem[];
  telemetry: EngineTelemetry | null;
  clock: ClockState;
}

export interface HealthResponse {
  status: string;
  python_version: string;
  engine: string;
  model_loaded: boolean;
  default_depth: number;
  device: string;
}

export interface ArchitectureStage {
  step: number;
  name: string;
  description: string;
  shape?: number[];
  parameters?: string;
}

export interface ExhibitionDataResponse {
  architecture: {
    title: string;
    stages: ArchitectureStage[];
  };
  benchmarks: {
    title: string;
    evaluator: string;
    test_suite: string;
    summary: {
      depth2_median_cpl: number;
      depth2_avg_cpl: number;
      pct_under_100_cp: number;
      pct_under_200_cp: number;
      regression_agreement: string;
      depth3_median_cpl: number;
      depth3_pct_under_100_cp: number;
    };
    disclaimer: string;
  };
}
