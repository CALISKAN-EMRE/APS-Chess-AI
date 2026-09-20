import React from 'react';
import { Piece } from './Piece';

interface PromotionModalProps {
  color: 'white' | 'black';
  onSelect: (pieceType: 'q' | 'r' | 'b' | 'n') => void;
  onCancel: () => void;
}

export const PromotionModal: React.FC<PromotionModalProps> = ({
  color,
  onSelect,
  onCancel,
}) => {
  const prefix = color === 'white' ? 'w' : 'b';
  const pieces: Array<{ type: 'q' | 'r' | 'b' | 'n'; label: string }> = [
    { type: 'q', label: 'Queen' },
    { type: 'r', label: 'Rook' },
    { type: 'b', label: 'Bishop' },
    { type: 'n', label: 'Knight' },
  ];

  return (
    <div
      className="drawer-backdrop"
      onClick={onCancel}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        className="panel-container"
        onClick={(e) => e.stopPropagation()}
        style={{
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '16px',
          background: 'var(--surface-panel)',
          border: '1px solid var(--aps-red-border)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: '0 20px 40px rgba(0,0,0,0.8)',
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <h3 className="font-display" style={{ fontSize: '16px', fontWeight: 600 }}>
            Pawn Promotion
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Select promotion piece
          </p>
        </div>

        <div style={{ display: 'flex', gap: '14px' }}>
          {pieces.map(({ type, label }) => (
            <button
              key={type}
              onClick={() => onSelect(type)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '8px',
                padding: '12px 16px',
                background: 'var(--surface-card)',
                border: '1px solid var(--surface-border)',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--aps-red)';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--surface-border)';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <div style={{ width: '48px', height: '48px' }}>
                <Piece piece={`${prefix}${type.toUpperCase()}`} />
              </div>
              <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                {label}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
