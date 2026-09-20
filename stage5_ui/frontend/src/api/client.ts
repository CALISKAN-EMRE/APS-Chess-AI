import type {
  GameStateResponse,
  HealthResponse,
  ExhibitionDataResponse,
} from '../types';

const API_BASE = '/api';

export class EngineBusyError extends Error {
  constructor(message: string = 'Engine is currently calculating a move.') {
    super(message);
    this.name = 'EngineBusyError';
  }
}

function logClientTrace(direction: 'REQ' | 'RESP', endpoint: string, data?: any) {
  const ts = new Date().toISOString().slice(11, 23);
  const prefix = direction === 'REQ' ? '➡️ [CLIENT REQ]' : '⬅️ [CLIENT RESP]';
  console.log(`${prefix} ${endpoint} at ${ts}`, data ?? '');
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`);
  }
  return res.json();
}

export async function newGame(
  humanColor: 'white' | 'black' = 'white',
  depth: number = 2,
  timeControl: number = 180,
  signal?: AbortSignal
): Promise<GameStateResponse> {
  logClientTrace('REQ', 'POST /api/game/new', { humanColor, depth, timeControl });
  const res = await fetch(`${API_BASE}/game/new`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ human_color: humanColor, depth, time_control: timeControl }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to start new game');
  }
  const data: GameStateResponse = await res.json();
  logClientTrace('RESP', 'POST /api/game/new', { game_id: data.game_id, version: data.version, fen: data.fen });
  return data;
}

export async function sendMove(
  move: string,
  gameId?: string,
  expectedVersion?: number,
  signal?: AbortSignal
): Promise<GameStateResponse> {
  logClientTrace('REQ', 'POST /api/game/move', { move, gameId, expectedVersion });
  const res = await fetch(`${API_BASE}/game/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      move,
      game_id: gameId,
      expected_version: expectedVersion,
    }),
    signal,
  });
  if (res.status === 409) {
    logClientTrace('RESP', 'POST /api/game/move [409 CONFLICT - BUSY]');
    throw new EngineBusyError('Engine is currently calculating a move. Please wait.');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to send move');
  }
  const data: GameStateResponse = await res.json();
  logClientTrace('RESP', 'POST /api/game/move', { game_id: data.game_id, version: data.version, fen: data.fen });
  return data;
}

export async function requestEngineMove(
  gameId?: string,
  expectedVersion?: number,
  signal?: AbortSignal
): Promise<GameStateResponse> {
  logClientTrace('REQ', 'POST /api/engine/move', { gameId, expectedVersion });
  const res = await fetch(`${API_BASE}/engine/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_id: gameId,
      expected_version: expectedVersion,
    }),
    signal,
  });
  if (res.status === 409) {
    logClientTrace('RESP', 'POST /api/engine/move [409 CONFLICT - BUSY]');
    throw new EngineBusyError('Engine is currently calculating a move. Please wait.');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Engine move request failed');
  }
  const data: GameStateResponse = await res.json();
  logClientTrace('RESP', 'POST /api/engine/move', { game_id: data.game_id, version: data.version, fen: data.fen });
  return data;
}

export async function fetchGameState(signal?: AbortSignal): Promise<GameStateResponse> {
  logClientTrace('REQ', 'GET /api/game/state');
  const res = await fetch(`${API_BASE}/game/state`, { signal });
  if (!res.ok) {
    throw new Error(`Failed to fetch game state: ${res.statusText}`);
  }
  const data: GameStateResponse = await res.json();
  logClientTrace('RESP', 'GET /api/game/state', { game_id: data.game_id, version: data.version, fen: data.fen });
  return data;
}

export async function fetchExhibitionData(): Promise<ExhibitionDataResponse> {
  const res = await fetch(`${API_BASE}/exhibition/data`);
  if (!res.ok) {
    throw new Error(`Failed to fetch exhibition data: ${res.statusText}`);
  }
  return res.json();
}
