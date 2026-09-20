import React from 'react';
import type { CapturedPieces } from '../../types';
import { Piece } from '../board/Piece';

interface CapturedTrayProps {
  captured: CapturedPieces;
  humanColor: 'white' | 'black';
  isPlayer?: boolean;
}

export const CapturedTray: React.FC<CapturedTrayProps> = ({
  captured,
  humanColor,
  isPlayer = true,
}) => {
  // If isPlayer is true: captured pieces are of the OPPONENT's color (captured by Player)
  // If isPlayer is false: captured pieces are of the PLAYER's color (captured by AI)
  const pieceList = isPlayer
    ? humanColor === 'white'
      ? captured.black
      : captured.white
    : humanColor === 'white'
    ? captured.white
    : captured.black;

  const capturedPieceColor = isPlayer
    ? humanColor === 'white'
      ? 'b'
      : 'w'
    : humanColor === 'white'
    ? 'w'
    : 'b';

  // Material advantage from this side's perspective
  const netAdvantage = isPlayer
    ? humanColor === 'white'
      ? captured.material_advantage
      : -captured.material_advantage
    : humanColor === 'white'
    ? -captured.material_advantage
    : captured.material_advantage;

  const getPieceCode = (pieceName: string) => {
    const p = pieceName.toLowerCase();
    const type = p === 'knight' ? 'N' : p[0].toUpperCase();
    return `${capturedPieceColor}${type}`;
  };

  if (pieceList.length === 0 && netAdvantage <= 0) {
    return null;
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 8px',
        borderRadius: 'var(--radius-sm)',
        background: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid rgba(255, 255, 255, 0.06)',
      }}
    >
      <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
        {pieceList.map((piece, idx) => (
          <div
            key={idx}
            style={{
              width: '16px',
              height: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            title={piece}
          >
            <Piece piece={getPieceCode(piece)} size="16px" />
          </div>
        ))}
      </div>

      {netAdvantage > 0 && (
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '10px',
            fontWeight: 700,
            color: isPlayer ? '#34d399' : '#f87171',
            marginLeft: '4px',
          }}
        >
          +{netAdvantage}
        </span>
      )}
    </div>
  );
};
