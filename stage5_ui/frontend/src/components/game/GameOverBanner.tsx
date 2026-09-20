import React, { useEffect, useState } from 'react';
import confetti from 'canvas-confetti';
import type { GameStatus } from '../../types';
import { Trophy, Award, RotateCcw, Eye } from 'lucide-react';

interface GameOverBannerProps {
  status: GameStatus;
  humanColor: 'white' | 'black';
  onNewGame: () => void;
}

export const GameOverBanner: React.FC<GameOverBannerProps> = ({
  status,
  humanColor,
  onNewGame,
}) => {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    setDismissed(false);
  }, [status.is_over]);

  const isHumanWinner = status.winner === humanColor;
  const isDraw = status.winner === null;

  useEffect(() => {
    if (status.is_over && isHumanWinner) {
      try {
        confetti({
          particleCount: 100,
          spread: 80,
          origin: { y: 0.55 },
          colors: ['#ab1818', '#ffffff', '#c92a2a'],
        });
      } catch {}
    }
  }, [status.is_over, isHumanWinner]);

  if (!status.is_over || dismissed) return null;

  return (
    <div className="drawer-backdrop" onClick={() => setDismissed(true)}>
      <div
        className="drawer-modal"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: '460px',
          textAlign: 'center',
          alignItems: 'center',
          padding: '32px 24px',
          gap: '16px',
        }}
      >
        {/* Victory/Defeat Icon */}
        <div
          style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            background: isHumanWinner
              ? 'rgba(34, 197, 94, 0.15)'
              : isDraw
              ? 'rgba(148, 163, 184, 0.15)'
              : 'rgba(171, 24, 24, 0.15)',
            border: `2px solid ${
              isHumanWinner ? '#22c55e' : isDraw ? '#94a3b8' : 'var(--aps-red)'
            }`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: isHumanWinner ? '0 0 24px rgba(34, 197, 94, 0.3)' : '0 0 24px rgba(171, 24, 24, 0.3)',
          }}
        >
          {isHumanWinner ? (
            <Trophy size={32} color="#22c55e" />
          ) : (
            <Award size={32} color={isDraw ? '#94a3b8' : 'var(--aps-red)'} />
          )}
        </div>

        {/* Title */}
        <div>
          <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Match Concluded
          </span>
          <h2
            className="font-display"
            style={{
              fontSize: '22px',
              fontWeight: 700,
              color: '#ffffff',
              marginTop: '4px',
            }}
          >
            {isHumanWinner
              ? 'Victory! You Won'
              : isDraw
              ? 'Game Drawn'
              : 'Engine Victory'}
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            {status.reason || 'Game completed.'}
          </p>
          <div
            style={{
              display: 'inline-block',
              marginTop: '8px',
              padding: '2px 10px',
              borderRadius: '4px',
              background: 'rgba(255, 255, 255, 0.05)',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              fontWeight: 700,
              color: '#ffffff',
            }}
          >
            Score: {status.result}
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '10px', width: '100%', marginTop: '8px' }}>
          <button
            onClick={onNewGame}
            className="aps-btn aps-btn-primary"
            style={{ flex: 1, height: '36px', fontSize: '13px' }}
          >
            <RotateCcw size={14} />
            <span>Rematch / New Game</span>
          </button>
          <button
            onClick={() => setDismissed(true)}
            className="aps-btn aps-btn-secondary"
            style={{ height: '36px', padding: '0 14px', fontSize: '13px' }}
            title="Inspect the final board position"
          >
            <Eye size={14} />
            <span>Review Board</span>
          </button>
        </div>
      </div>
    </div>
  );
};
