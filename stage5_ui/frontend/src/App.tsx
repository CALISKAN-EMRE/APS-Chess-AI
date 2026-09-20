import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Header } from './components/layout/Header';
import { Chessboard } from './components/board/Chessboard';
import { EngineStatusPanel } from './components/engine/EngineStatusPanel';
import { GameControls } from './components/game/GameControls';
import { MoveHistory } from './components/game/MoveHistory';
import { CapturedTray } from './components/game/CapturedTray';
import { GameOverBanner } from './components/game/GameOverBanner';
import { ChessClock } from './components/game/ChessClock';
import { ArchitectureView } from './components/exhibition/ArchitectureView';
import { BenchmarkView } from './components/exhibition/BenchmarkView';
import { newGame, sendMove, requestEngineMove, fetchGameState, EngineBusyError } from './api/client';
import type { GameStateResponse } from './types';
import { User, AlertCircle } from 'lucide-react';

export const App: React.FC = () => {
  const [gameState, setGameState] = useState<GameStateResponse | null>(null);
  const [isThinking, setIsThinking] = useState<boolean>(false);
  const [orientation, setOrientation] = useState<'white' | 'black'>('white');
  const [activeDrawer, setActiveDrawer] = useState<'architecture' | 'benchmark' | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Local displayed clock times for high-frequency countdown animation
  const [remainingClocks, setRemainingClocks] = useState<{ white: number; black: number }>({
    white: 180,
    black: 180,
  });

  const clockSyncRef = useRef<{
    white: number;
    black: number;
    activeClock: 'white' | 'black' | null;
    syncTimestamp: number;
  }>({
    white: 180,
    black: 180,
    activeClock: 'white',
    syncTimestamp: performance.now(),
  });

  // Synchronization refs to prevent concurrency, race conditions, and StrictMode duplicates
  const activeAbortController = useRef<AbortController | null>(null);
  const activeGameIdRef = useRef<string | null>(null);
  const activeVersionRef = useRef<number>(0);
  const isThinkingRef = useRef<boolean>(false);
  const initializedRef = useRef<boolean>(false);

  // Trigger engine move separately with strict session and version tracking
  const triggerEngineMove = useCallback(async (expectedGameId: string, afterVersion: number) => {
    if (isThinkingRef.current) return;
    setIsThinking(true);
    isThinkingRef.current = true;
    setErrorMsg(null);

    const controller = new AbortController();
    activeAbortController.current = controller;

    try {
      console.log(`[STATE SYNC] Requesting engine move for game ${expectedGameId} (version > ${afterVersion})`);
      const aiData = await requestEngineMove(expectedGameId, afterVersion, controller.signal);

      // Verify that the response still belongs to the active game session
      if (activeGameIdRef.current !== expectedGameId) {
        console.warn(`[STALE AI RESPONSE DISCARDED] Response for game ${aiData.game_id} discarded; active game is ${activeGameIdRef.current}`);
        return;
      }
      if (aiData.version <= activeVersionRef.current) {
        console.warn(`[STALE AI VERSION DISCARDED] Response version ${aiData.version} <= active ${activeVersionRef.current}`);
        return;
      }

      activeVersionRef.current = aiData.version;
      setGameState(aiData);
      console.log(`[STATE SYNC] AI move received: ${aiData.last_move?.san} (version ${aiData.version})`);
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('[STATE SYNC] Engine move request was aborted.');
        return;
      }
      if (err instanceof EngineBusyError) {
        setErrorMsg('AI engine is currently calculating. Please wait.');
        return;
      }
      setErrorMsg(err.message || 'Engine move failed.');
    } finally {
      setIsThinking(false);
      isThinkingRef.current = false;
    }
  }, []);

  // Explicitly start a fresh game session (only invoked on explicit Restart / New Game)
  const initGame = useCallback(async (color: 'white' | 'black' = 'white', depth: number = 2, timeControl: number = 180) => {
    // 1. Cancel any active in-flight HTTP requests
    if (activeAbortController.current) {
      activeAbortController.current.abort();
    }
    const controller = new AbortController();
    activeAbortController.current = controller;

    activeGameIdRef.current = null;
    setIsThinking(false);
    isThinkingRef.current = false;
    setErrorMsg(null);

    try {
      const data = await newGame(color, depth, timeControl, controller.signal);
      activeGameIdRef.current = data.game_id;
      activeVersionRef.current = data.version;
      setGameState(data);
      setOrientation(color);
      console.log(`[STATE SYNC] Initialized fresh game ${data.game_id} (version ${data.version}, turn: ${data.turn}, tc: ${timeControl}s)`);

      // If human chose Black, engine moves first as White
      if (color === 'black' && data.turn === 'white') {
        triggerEngineMove(data.game_id, data.version);
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('[STATE SYNC] Previous newGame request was aborted.');
        return;
      }
      setErrorMsg(err.message || 'Failed to initialize chess game.');
    }
  }, [triggerEngineMove]);

  // Whenever gameState changes, update clock anchor
  useEffect(() => {
    if (gameState?.clock) {
      clockSyncRef.current = {
        white: gameState.clock.white_time,
        black: gameState.clock.black_time,
        activeClock: gameState.clock.active_clock,
        syncTimestamp: performance.now(),
      };
      setRemainingClocks({
        white: gameState.clock.white_time,
        black: gameState.clock.black_time,
      });
    }
  }, [
    gameState?.clock?.white_time,
    gameState?.clock?.black_time,
    gameState?.clock?.active_clock,
    gameState?.clock?.game_started,
    gameState?.version,
  ]);

  // High-frequency smooth countdown ticker anchored to backend monotonic timestamps
  useEffect(() => {
    if (!gameState || gameState.game_status.is_over || !gameState.clock?.game_started) return;

    const interval = setInterval(() => {
      const { white, black, activeClock, syncTimestamp } = clockSyncRef.current;
      if (!activeClock) return;

      const elapsed = (performance.now() - syncTimestamp) / 1000;
      if (activeClock === 'white') {
        const currentWhite = Math.max(0, white - elapsed);
        setRemainingClocks({ white: currentWhite, black });
        if (currentWhite <= 0 && !gameState.game_status.is_over) {
          fetchGameState().then((latest) => latest && setGameState(latest)).catch(() => {});
        }
      } else if (activeClock === 'black') {
        const currentBlack = Math.max(0, black - elapsed);
        setRemainingClocks({ white, black: currentBlack });
        if (currentBlack <= 0 && !gameState.game_status.is_over) {
          fetchGameState().then((latest) => latest && setGameState(latest)).catch(() => {});
        }
      }
    }, 100);

    return () => clearInterval(interval);
  }, [gameState?.game_status.is_over, gameState?.clock?.active_clock, gameState?.clock?.game_started]);

  // Page Load / F5 Refresh: Restore active backend game if one exists; otherwise initialize clean game
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const restoreOrInit = async () => {
      try {
        const activeState = await fetchGameState();
        if (activeState && activeState.game_id && activeState.version > 0) {
          activeGameIdRef.current = activeState.game_id;
          activeVersionRef.current = activeState.version;
          setGameState(activeState);
          setOrientation(activeState.human_color as 'white' | 'black');
          console.log(`[STATE SYNC] Restored active session on load/refresh: ${activeState.game_id} (version ${activeState.version})`);
          return;
        }
      } catch {
        console.log('[STATE SYNC] No existing session found, creating initial game');
      }

      // If no valid session exists on backend, initialize default clean game
      initGame('white', 2, 180);
    };

    restoreOrInit();

    return () => {
      activeAbortController.current?.abort();
    };
  }, [initGame]);

  // Handle human move: validates and renders human move immediately, then requests AI move separately
  const handleMakeMove = async (uci: string) => {
    if (!gameState || isThinking || isThinkingRef.current || gameState.game_status.is_over) {
      console.warn('[MOVE REJECTED CLIENT-SIDE] Engine busy or game over.');
      return;
    }
    if (gameState.turn !== gameState.human_color) {
      console.warn('[MOVE REJECTED CLIENT-SIDE] Not human turn.');
      return;
    }

    const currentGameId = activeGameIdRef.current;
    const currentVersion = activeVersionRef.current;
    if (!currentGameId) return;

    setErrorMsg(null);

    // Cancel any previous request
    if (activeAbortController.current) {
      activeAbortController.current.abort();
    }
    const controller = new AbortController();
    activeAbortController.current = controller;

    try {
      // 1. Submit human move - server validates, pushes move, and immediately returns (<15ms)
      const humanUpdated = await sendMove(uci, currentGameId, currentVersion, controller.signal);

      // Verify response integrity
      if (activeGameIdRef.current !== currentGameId || humanUpdated.version <= activeVersionRef.current) {
        console.warn('[STALE HUMAN RESPONSE DISCARDED]');
        return;
      }

      activeVersionRef.current = humanUpdated.version;
      // 2. Render human move immediately onto the board
      setGameState(humanUpdated);
      console.log(`[STATE SYNC] Human move applied immediately: ${uci} (version ${humanUpdated.version})`);

      // 3. If game is not over, enter AI_THINKING state and request engine move separately
      if (!humanUpdated.game_status.is_over) {
        triggerEngineMove(humanUpdated.game_id, humanUpdated.version);
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('[STATE SYNC] Move request was aborted.');
        return;
      }
      if (err instanceof EngineBusyError) {
        setErrorMsg('AI engine is currently calculating. Please wait.');
        return;
      }
      setErrorMsg(err.message || 'Move rejected by server.');
    }
  };

  const handleFlipBoard = () => {
    setOrientation((prev) => (prev === 'white' ? 'black' : 'white'));
  };

  const handleResign = () => {
    if (!gameState || isThinking) return;
    setGameState((prev) =>
      prev
        ? {
            ...prev,
            game_status: {
              is_over: true,
              winner: prev.human_color === 'white' ? 'black' : 'white',
              reason: 'Player resigned.',
              result: prev.human_color === 'white' ? '0-1' : '1-0',
              is_check: false,
            },
          }
        : null
    );
  };

  const topColor = orientation === 'white' ? 'black' : 'white';
  const bottomColor = orientation === 'white' ? 'white' : 'black';
  const isTopHuman = gameState ? gameState.human_color === topColor : false;

  const renderPlayerStatus = (isPlayer: boolean, color: 'white' | 'black') => {
    if (!gameState) return null;

    if (gameState.game_status.is_over) {
      if (gameState.game_status.winner === color) {
        return (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              fontWeight: 600,
              color: '#34d399',
              background: 'var(--status-ready-bg)',
              padding: '1px 6px',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--status-ready-border)',
              letterSpacing: '0.04em',
            }}
          >
            WINNER
          </span>
        );
      }
      return null;
    }

    if (!gameState.clock?.game_started) {
      if (!isPlayer && isThinking) {
        return (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              fontWeight: 600,
              color: '#fca5a5',
              background: 'var(--status-computing-bg)',
              padding: '1px 6px',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--status-computing-border)',
              letterSpacing: '0.04em',
            }}
          >
            AI THINKING
          </span>
        );
      }
      if (color === 'white') {
        return (
          <span
            id="status-game-ready"
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              fontWeight: 600,
              color: '#38bdf8',
              background: 'rgba(56, 189, 248, 0.12)',
              padding: '1px 6px',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid rgba(56, 189, 248, 0.28)',
              letterSpacing: '0.04em',
            }}
          >
            GAME READY · WHITE TO MOVE
          </span>
        );
      }
      return null;
    }

    const isCurrentTurn = gameState.turn === color;
    if (isCurrentTurn) {
      if (gameState.game_status.is_check) {
        return (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              fontWeight: 600,
              color: '#f59e0b',
              background: 'rgba(245, 158, 11, 0.14)',
              padding: '1px 6px',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              letterSpacing: '0.04em',
            }}
          >
            CHECK
          </span>
        );
      }
      if (isPlayer) {
        return (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              fontWeight: 600,
              color: '#34d399',
              background: 'var(--status-ready-bg)',
              padding: '1px 6px',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--status-ready-border)',
              letterSpacing: '0.04em',
            }}
          >
            YOUR TURN
          </span>
        );
      } else {
        return (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              fontWeight: 600,
              color: '#fca5a5',
              background: 'var(--status-computing-bg)',
              padding: '1px 6px',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--status-computing-border)',
              letterSpacing: '0.04em',
            }}
          >
            AI THINKING
          </span>
        );
      }
    } else {
      if (!isPlayer && gameState.last_move && gameState.last_move.color === color) {
        return (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              fontWeight: 600,
              color: '#93c5fd',
              background: 'rgba(59, 130, 246, 0.12)',
              padding: '1px 6px',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid rgba(59, 130, 246, 0.25)',
              letterSpacing: '0.04em',
            }}
          >
            AI MOVED
          </span>
        );
      }
      return null;
    }
  };

  return (
    <div className="app-shell">
      {/* Exhibition Top Navigation Bar */}
      <Header
        onOpenArchitecture={() => setActiveDrawer('architecture')}
        onOpenBenchmark={() => setActiveDrawer('benchmark')}
        depth={gameState?.depth ?? 2}
        isThinking={isThinking}
        gameStarted={gameState?.clock?.game_started ?? false}
        isOver={gameState?.game_status?.is_over ?? false}
      />

      {/* Main Exhibition Workspace: Chessboard Stage + Unified Instrument Console */}
      <main className="exhibition-workspace">
        {/* LEFT COLUMN: HERO CHESSBOARD & PLAYER STRIPS */}
        <section className="board-stage">
          {/* Top Player Strip */}
          <div className="player-strip">
            {isTopHuman ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div
                  style={{
                    width: '18px',
                    height: '18px',
                    borderRadius: '2px',
                    background: 'var(--surface-elevated)',
                    border: '1px solid var(--surface-border-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <User size={12} color="var(--text-secondary)" />
                </div>
                <span className="font-display" style={{ fontWeight: 600, color: '#ffffff', letterSpacing: '0.02em' }}>
                  Guest Challenger
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  · {topColor === 'white' ? 'White' : 'Black'}
                </span>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <img
                  src="/ml_logo.png"
                  alt="APS ML"
                  style={{ height: '18px', width: 'auto', objectFit: 'contain' }}
                />
                <span className="font-display" style={{ fontWeight: 600, color: '#ffffff', letterSpacing: '0.02em' }}>
                  APS Deep Value Engine v1
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  · Depth {gameState?.depth ?? 2}
                </span>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {gameState && (
                <CapturedTray
                  captured={gameState.captured}
                  humanColor={gameState.human_color}
                  isPlayer={isTopHuman}
                />
              )}
              {gameState && (
                <ChessClock
                  color={topColor}
                  remainingSeconds={topColor === 'white' ? remainingClocks.white : remainingClocks.black}
                  isActive={gameState.clock?.active_clock === topColor && !gameState.game_status.is_over}
                  isGameOver={gameState.game_status.is_over}
                />
              )}
              {renderPlayerStatus(isTopHuman, topColor)}
            </div>
          </div>

          {/* Center Stage: Integrated Hero Chessboard with Evaluation Gauge */}
          <div className="board-stage-center">
            <Chessboard
              fen={gameState?.fen ?? 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'}
              orientation={orientation}
              evaluation={gameState?.telemetry?.evaluation ?? 0.0}
              legalMoves={gameState?.legal_moves ?? []}
              lastMove={gameState?.last_move ?? null}
              isCheck={gameState?.game_status.is_check ?? false}
              turn={gameState?.turn ?? 'white'}
              humanColor={gameState?.human_color ?? 'white'}
              isThinking={isThinking}
              onMakeMove={handleMakeMove}
            />
          </div>

          {/* Bottom Player Strip */}
          <div className="player-strip">
            {!isTopHuman ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div
                  style={{
                    width: '18px',
                    height: '18px',
                    borderRadius: '2px',
                    background: 'var(--surface-elevated)',
                    border: '1px solid var(--surface-border-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <User size={12} color="var(--text-secondary)" />
                </div>
                <span className="font-display" style={{ fontWeight: 600, color: '#ffffff', letterSpacing: '0.02em' }}>
                  Guest Challenger
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  · {topColor === 'white' ? 'Black' : 'White'}
                </span>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <img
                  src="/ml_logo.png"
                  alt="APS ML"
                  style={{ height: '18px', width: 'auto', objectFit: 'contain' }}
                />
                <span className="font-display" style={{ fontWeight: 600, color: '#ffffff', letterSpacing: '0.02em' }}>
                  APS Deep Value Engine v1
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  · Depth {gameState?.depth ?? 2}
                </span>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {gameState && (
                <CapturedTray
                  captured={gameState.captured}
                  humanColor={gameState.human_color}
                  isPlayer={!isTopHuman}
                />
              )}
              {gameState && (
                <ChessClock
                  color={bottomColor}
                  remainingSeconds={bottomColor === 'white' ? remainingClocks.white : remainingClocks.black}
                  isActive={gameState.clock?.active_clock === bottomColor && !gameState.game_status.is_over}
                  isGameOver={gameState.game_status.is_over}
                />
              )}
              {renderPlayerStatus(!isTopHuman, bottomColor)}
            </div>
          </div>
        </section>

        {/* RIGHT COLUMN: UNIFIED PRECISION INSTRUMENT CONSOLE */}
        <aside className="engine-stage">
          <div className="instrument-console">
            <EngineStatusPanel
              telemetry={gameState?.telemetry ?? null}
              lastMove={gameState?.last_move ?? null}
              isThinking={isThinking}
              depth={gameState?.depth ?? 2}
              isOver={gameState?.game_status.is_over ?? false}
              turn={gameState?.turn ?? 'white'}
              humanColor={gameState?.human_color ?? 'white'}
              gameStarted={gameState?.clock?.game_started ?? false}
              isCheck={gameState?.game_status.is_check ?? false}
              winner={gameState?.game_status.winner ?? null}
              reason={gameState?.game_status.reason ?? null}
            />

            <div className="console-divider" />

            <GameControls
              humanColor={gameState?.human_color ?? 'white'}
              depth={gameState?.depth ?? 2}
              timeControl={gameState?.clock?.time_control ?? 180}
              isThinking={isThinking}
              onNewGame={initGame}
              onFlipBoard={handleFlipBoard}
              onResign={handleResign}
              isGameOver={gameState?.game_status.is_over ?? false}
            />

            <MoveHistory history={gameState?.history ?? []} />
          </div>
        </aside>
      </main>

      {/* Floating Error Notification (Never triggers layout shifting) */}
      {errorMsg && (
        <div
          style={{
            position: 'fixed',
            bottom: '16px',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '8px 16px',
            background: 'rgba(239, 68, 68, 0.95)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
            borderRadius: 'var(--radius-md)',
            color: '#ffffff',
            fontSize: '12px',
            fontWeight: 500,
          }}
        >
          <AlertCircle size={15} />
          <span>{errorMsg}</span>
          <button
            onClick={() => setErrorMsg(null)}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#ffffff',
              cursor: 'pointer',
              padding: '0 4px',
              fontWeight: 700,
              marginLeft: '6px',
              fontSize: '14px',
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
      )}

      {/* Modal Game Over Banner */}
      {gameState && (
        <GameOverBanner
          status={gameState.game_status}
          humanColor={gameState.human_color}
          onNewGame={() => initGame(gameState.human_color, gameState.depth, gameState.clock?.time_control ?? 180)}
        />
      )}

      {/* Modal Exhibition Drawers */}
      {activeDrawer === 'architecture' && (
        <ArchitectureView onClose={() => setActiveDrawer(null)} />
      )}
      {activeDrawer === 'benchmark' && (
        <BenchmarkView onClose={() => setActiveDrawer(null)} />
      )}
    </div>
  );
};

export default App;
