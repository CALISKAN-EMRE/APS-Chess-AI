import React from 'react';

interface SquareProps {
  square: string; // e.g., 'e4'
  isLight: boolean;
  isSelected: boolean;
  isLastMove: boolean;
  isCheck: boolean;
  isLegalTarget: boolean;
  hasPieceToCapture: boolean;
  rankLabel?: string | null;
  fileLabel?: string | null;
  onClick: () => void;
  onDrop?: () => void;
  onDragOver?: (e: React.DragEvent) => void;
  children?: React.ReactNode;
}

export const Square: React.FC<SquareProps> = ({
  square,
  isLight,
  isSelected,
  isLastMove,
  isCheck,
  isLegalTarget,
  hasPieceToCapture,
  rankLabel,
  fileLabel,
  onClick,
  onDrop,
  onDragOver,
  children,
}) => {
  const classNames = [
    'square',
    isLight ? 'light' : 'dark',
    isSelected ? 'selected' : '',
    isLastMove ? 'last-move' : '',
    isCheck ? 'check' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      id={`sq-${square}`}
      className={classNames}
      onClick={onClick}
      onDragOver={(e) => {
        if (onDragOver) {
          e.preventDefault();
          onDragOver(e);
        }
      }}
      onDrop={(e) => {
        if (onDrop) {
          e.preventDefault();
          onDrop();
        }
      }}
    >
      {/* Rank coordinate */}
      {rankLabel && <span className="coord-rank">{rankLabel}</span>}

      {/* File coordinate */}
      {fileLabel && <span className="coord-file">{fileLabel}</span>}

      {/* Piece Vector */}
      {children}

      {/* Precision Legal Move Indicators */}
      {isLegalTarget && (
        hasPieceToCapture ? (
          <div className="legal-capture-bracket" />
        ) : (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
            }}
          >
            <div className="legal-dot" />
          </div>
        )
      )}
    </div>
  );
};
