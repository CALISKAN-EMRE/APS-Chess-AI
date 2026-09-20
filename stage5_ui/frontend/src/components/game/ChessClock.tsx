import React from 'react';
import { Timer } from 'lucide-react';

interface ChessClockProps {
  color: 'white' | 'black';
  remainingSeconds: number;
  isActive: boolean;
  isGameOver: boolean;
}

export function formatClockTime(seconds: number): string {
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  const remS = Math.floor(s % 60);
  if (s < 10) {
    const tenths = Math.floor((s % 1) * 10);
    return `${m}:${remS.toString().padStart(2, '0')}.${tenths}`;
  }
  return `${m}:${remS.toString().padStart(2, '0')}`;
}

export const ChessClock: React.FC<ChessClockProps> = ({
  color,
  remainingSeconds,
  isActive,
  isGameOver,
}) => {
  const isUrgent = remainingSeconds > 0 && remainingSeconds <= 10 && !isGameOver;
  const isExpired = remainingSeconds <= 0;

  const clockClass = [
    'chess-clock-badge',
    isActive ? 'clock-active' : '',
    isUrgent ? 'clock-urgent' : '',
    isExpired ? 'clock-expired' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      id={`clock-${color}`}
      className={clockClass}
      title={`${color === 'white' ? 'White' : 'Black'} clock: ${remainingSeconds.toFixed(1)}s`}
    >
      <Timer
        size={11}
        style={{
          opacity: isActive ? 1 : 0.45,
          color: isUrgent || isExpired ? '#fca5a5' : isActive ? '#ffffff' : 'var(--text-muted)',
          flexShrink: 0,
        }}
      />
      <span className="clock-time-display">{formatClockTime(remainingSeconds)}</span>
    </div>
  );
};
