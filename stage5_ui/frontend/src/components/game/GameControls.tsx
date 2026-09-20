import React, { useState, useEffect } from 'react';
import { RotateCw, Play, Flag } from 'lucide-react';

interface GameControlsProps {
  humanColor: 'white' | 'black';
  depth: number;
  timeControl?: number;
  isThinking: boolean;
  onNewGame: (color: 'white' | 'black', depth: number, timeControl: number) => void;
  onFlipBoard: () => void;
  onResign: () => void;
  isGameOver: boolean;
}

export const GameControls: React.FC<GameControlsProps> = ({
  humanColor,
  depth,
  timeControl = 180,
  isThinking,
  onNewGame,
  onFlipBoard,
  onResign,
  isGameOver,
}) => {
  const [selectedColor, setSelectedColor] = useState<'white' | 'black'>(humanColor);
  const [selectedDepth, setSelectedDepth] = useState<number>(depth);
  const [selectedTimeControl, setSelectedTimeControl] = useState<number>(timeControl);

  useEffect(() => {
    setSelectedColor(humanColor);
  }, [humanColor]);

  useEffect(() => {
    setSelectedDepth(depth);
  }, [depth]);

  useEffect(() => {
    setSelectedTimeControl(timeControl);
  }, [timeControl]);

  const handleStartNewGame = () => {
    onNewGame(selectedColor, selectedDepth, selectedTimeControl);
  };

  return (
    <div className="controls-section">
      {/* Recessed Segmented Physical Channels */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        {/* Play As Segmented Switch */}
        <div>
          <div
            style={{
              fontSize: '10px',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              color: 'var(--text-muted)',
              marginBottom: '4px',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Challenger Side
          </div>
          <div className="segmented-channel" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <button
              id="btn-choose-white"
              onClick={() => setSelectedColor('white')}
              disabled={isThinking}
              className={`segmented-pill ${selectedColor === 'white' ? 'active' : ''}`}
            >
              <span
                style={{
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  background: '#ffffff',
                  boxShadow: '0 0 2px rgba(0,0,0,0.5)',
                }}
              />
              White
            </button>
            <button
              id="btn-choose-black"
              onClick={() => setSelectedColor('black')}
              disabled={isThinking}
              className={`segmented-pill ${selectedColor === 'black' ? 'active' : ''}`}
            >
              <span
                style={{
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  background: '#1e293b',
                  border: '1px solid #64748b',
                }}
              />
              Black
            </button>
          </div>
        </div>

        {/* Time Control Segmented Switch */}
        <div>
          <div
            style={{
              fontSize: '10px',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              color: 'var(--text-muted)',
              marginBottom: '4px',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Time Control
          </div>
          <div className="segmented-channel" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <button
              id="btn-time-3m"
              onClick={() => setSelectedTimeControl(180)}
              disabled={isThinking}
              className={`segmented-pill ${selectedTimeControl === 180 ? 'active' : ''}`}
              title="3 min — 3+0 bullet chess clock"
            >
              3 MIN
            </button>
            <button
              id="btn-time-5m"
              onClick={() => setSelectedTimeControl(300)}
              disabled={isThinking}
              className={`segmented-pill ${selectedTimeControl === 300 ? 'active' : ''}`}
              title="5 min — 5+0 bullet chess clock"
            >
              5 MIN
            </button>
          </div>
        </div>
      </div>

      {/* Row 2: Search Depth + Subtle Recommendation */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.15fr 1fr', gap: '8px', alignItems: 'flex-end' }}>
        <div>
          <div
            style={{
              fontSize: '10px',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              color: 'var(--text-muted)',
              marginBottom: '4px',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Search Depth
          </div>
          <div className="segmented-channel" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
            {[
              { d: 1, label: 'D1' },
              { d: 2, label: 'D2 ★' },
              { d: 3, label: 'D3' },
            ].map(({ d, label }) => (
              <button
                key={d}
                id={`btn-depth-${d}`}
                onClick={() => setSelectedDepth(d)}
                disabled={isThinking}
                className={`segmented-pill ${selectedDepth === d ? 'active' : ''}`}
                title={`Engine depth ${d}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Subtle Depth Recommendation */}
        <div
          id="time-control-recommendation"
          style={{
            fontSize: '9.5px',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
            lineHeight: 1.35,
            paddingBottom: '5px',
            userSelect: 'none',
          }}
          title="Exhibition depth recommendation"
        >
          {selectedTimeControl === 180 ? (
            <span>
              <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>3 min</span> → D1 Fast recommended
            </span>
          ) : (
            <span>
              <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>5 min</span> → D2 recommended
            </span>
          )}
        </div>
      </div>

      {/* Action Row: Engineered Physical Tactile Buttons */}
      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
        <button
          id="btn-restart"
          onClick={handleStartNewGame}
          disabled={isThinking}
          className="aps-btn aps-btn-primary"
          style={{
            flex: 1,
            height: '32px',
            fontSize: '11px',
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
          }}
          title="Start fresh game with selected settings"
        >
          <Play size={12} fill="#ffffff" />
          <span>New Game</span>
        </button>

        <button
          onClick={onFlipBoard}
          className="aps-btn aps-btn-secondary"
          style={{
            height: '32px',
            width: '32px',
            padding: 0,
          }}
          title="Flip board orientation"
        >
          <RotateCw size={13} />
        </button>

        {!isGameOver && (
          <button
            onClick={onResign}
            disabled={isThinking}
            className="aps-btn aps-btn-secondary"
            style={{
              height: '32px',
              width: '32px',
              padding: 0,
              color: '#f87171',
            }}
            title="Resign game"
          >
            <Flag size={13} />
          </button>
        )}
      </div>
    </div>
  );
};
