import React from 'react';
import type { EngineTelemetry, MoveResult } from '../../types';

interface EngineStatusPanelProps {
  telemetry: EngineTelemetry | null;
  lastMove: MoveResult | null;
  isThinking: boolean;
  depth: number;
  isOver: boolean;
  turn: 'white' | 'black';
  humanColor: 'white' | 'black';
  gameStarted?: boolean;
  isCheck?: boolean;
  winner?: 'white' | 'black' | null;
  reason?: string | null;
}

export const EngineStatusPanel: React.FC<EngineStatusPanelProps> = ({
  telemetry,
  lastMove,
  isThinking,
  depth,
  isOver,
  turn,
  humanColor,
  gameStarted = false,
  isCheck = false,
  winner = null,
  reason = null,
}) => {
  let stateTitle = 'GAME READY';
  let stateStyle = { color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.12)', border: 'rgba(56, 189, 248, 0.28)' };

  if (isOver) {
    if (reason && reason.toLowerCase().includes('time')) {
      stateTitle = 'TIME OUT';
      stateStyle = { color: '#f87171', bg: 'rgba(239, 68, 68, 0.14)', border: 'rgba(239, 68, 68, 0.3)' };
    } else if (winner) {
      stateTitle = 'CHECKMATE';
      stateStyle = { color: '#f87171', bg: 'rgba(239, 68, 68, 0.14)', border: 'rgba(239, 68, 68, 0.3)' };
    } else {
      stateTitle = 'DRAW';
      stateStyle = { color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.12)', border: 'rgba(148, 163, 184, 0.25)' };
    }
  } else if (!gameStarted) {
    stateTitle = 'GAME READY';
    stateStyle = { color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.12)', border: 'rgba(56, 189, 248, 0.28)' };
  } else if (isThinking) {
    stateTitle = 'AI THINKING';
    stateStyle = { color: '#fca5a5', bg: 'rgba(171, 24, 24, 0.16)', border: 'rgba(171, 24, 24, 0.38)' };
  } else if (isCheck) {
    stateTitle = 'CHECK';
    stateStyle = { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.14)', border: 'rgba(245, 158, 11, 0.3)' };
  } else if (turn === humanColor) {
    stateTitle = 'YOUR TURN';
    stateStyle = { color: '#34d399', bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.28)' };
  } else {
    stateTitle = 'AI MOVED';
    stateStyle = { color: '#93c5fd', bg: 'rgba(59, 130, 246, 0.12)', border: 'rgba(59, 130, 246, 0.25)' };
  }

  const evalScore = telemetry?.evaluation ?? 0;
  const evalFormatted =
    evalScore > 0 ? `+${evalScore.toFixed(2)}` : evalScore.toFixed(2);

  return (
    <div className="telemetry-section">
      {/* Console Section Header: Title & Functional Status Indicator */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="console-section-header" style={{ padding: 0 }}>
          Engine Analysis
        </span>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '10px',
            fontWeight: 600,
            color: stateStyle.color,
            background: stateStyle.bg,
            border: `1px solid ${stateStyle.border}`,
            padding: '2px 7px',
            borderRadius: 'var(--radius-xs)',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
          }}
        >
          {stateTitle}
        </span>
      </div>

      {/* Hero Evaluation: Primary Engine Signal */}
      <div className="hero-eval-row">
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '3px' }}>
            <span
              className="hero-eval-value"
              style={{
                color:
                  evalScore > 0.15
                    ? '#ffffff'
                    : evalScore < -0.15
                    ? '#fca5a5'
                    : '#e2e8f0',
              }}
            >
              {evalFormatted}
            </span>
            <span className="hero-eval-unit">pts</span>
          </div>
          <span className="hero-eval-label">Position Evaluation</span>
        </div>

        <div style={{ textAlign: 'right' }}>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              fontWeight: 600,
              color: 'var(--text-secondary)',
            }}
          >
            {evalScore > 0 ? 'White is favored' : evalScore < 0 ? 'Black is favored' : 'Equal position'}
          </span>
          <div style={{ fontSize: '9px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
            APS Deep Value Engine v1
          </div>
        </div>
      </div>

      {/* Horizontal Monolithic Telemetry Strip: Secondary Metadata */}
      <div className="telemetry-strip">
        <div className="telemetry-item">
          <span className="telemetry-label">Depth</span>
          <span className="telemetry-val">D{depth}</span>
        </div>
        <div className="telemetry-item">
          <span className="telemetry-label">Search Time</span>
          <span
            className="telemetry-val"
            style={{ color: isThinking ? 'var(--aps-red)' : 'var(--text-primary)' }}
          >
            {isThinking ? '...' : telemetry ? `${telemetry.search_time.toFixed(2)}s` : '0.00s'}
          </span>
        </div>
        <div className="telemetry-item">
          <span className="telemetry-label">Nodes</span>
          <span className="telemetry-val">
            {telemetry ? telemetry.nodes_visited.toLocaleString() : '0'}
          </span>
        </div>
        <div className="telemetry-item">
          <span className="telemetry-label">NN Evals</span>
          <span className="telemetry-val">
            {telemetry ? telemetry.neural_evaluations.toLocaleString() : '0'}
          </span>
        </div>
        <div className="telemetry-item">
          <span className="telemetry-label">Cutoffs</span>
          <span className="telemetry-val">
            {telemetry ? telemetry.cutoffs.toLocaleString() : '0'}
          </span>
        </div>
      </div>

      {/* Subtle Last Move Subline */}
      {lastMove && (
        <div className="last-ply-bar">
          <span>
            Last Move: <strong style={{ color: '#ffffff' }}>{lastMove.san}</strong> ({lastMove.uci}) by {lastMove.color === 'white' ? 'White' : 'Black'}
          </span>
          <span style={{ color: 'var(--text-muted)' }}>
            D{depth}
          </span>
        </div>
      )}
    </div>
  );
};
