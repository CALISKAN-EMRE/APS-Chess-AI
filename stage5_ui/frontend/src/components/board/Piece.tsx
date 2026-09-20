import React from 'react';

import wK from '../../assets/pieces/cburnett/wK.svg';
import wQ from '../../assets/pieces/cburnett/wQ.svg';
import wR from '../../assets/pieces/cburnett/wR.svg';
import wB from '../../assets/pieces/cburnett/wB.svg';
import wN from '../../assets/pieces/cburnett/wN.svg';
import wP from '../../assets/pieces/cburnett/wP.svg';
import bK from '../../assets/pieces/cburnett/bK.svg';
import bQ from '../../assets/pieces/cburnett/bQ.svg';
import bR from '../../assets/pieces/cburnett/bR.svg';
import bB from '../../assets/pieces/cburnett/bB.svg';
import bN from '../../assets/pieces/cburnett/bN.svg';
import bP from '../../assets/pieces/cburnett/bP.svg';

const PIECE_MAP: Record<string, string> = {
  wK, wQ, wR, wB, wN, wP,
  bK, bQ, bR, bB, bN, bP,
};

interface PieceProps {
  piece: string; // e.g., 'wP', 'wN', 'wB', 'wR', 'wQ', 'wK', 'bP', 'bN', etc.
  size?: number | string;
}

export const Piece: React.FC<PieceProps> = ({ piece, size = '84%' }) => {
  // Normalize piece identifier: 'p' -> 'bP', 'P' -> 'wP', 'wP' -> 'wP', etc.
  let key = piece;
  if (piece.length === 1) {
    key = piece === piece.toUpperCase() ? `w${piece}` : `b${piece.toUpperCase()}`;
  } else if (piece.length === 2) {
    key = `${piece[0].toLowerCase() === 'w' ? 'w' : 'b'}${piece[1].toUpperCase()}`;
  }

  const src = PIECE_MAP[key];
  if (!src) return null;

  const isWhite = key.startsWith('w');

  return (
    <div
      className="chess-piece"
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        userSelect: 'none',
        WebkitUserSelect: 'none',
      }}
    >
      <img
        src={src}
        alt={key}
        draggable={false}
        style={{
          width: size,
          height: size,
          objectFit: 'contain',
          pointerEvents: 'none',
          filter: isWhite
            ? 'drop-shadow(0 2px 4px rgba(0, 0, 0, 0.4))'
            : 'drop-shadow(0 2px 5px rgba(0, 0, 0, 0.7))',
          transition: 'transform 0.15s ease-out',
        }}
      />
    </div>
  );
};
