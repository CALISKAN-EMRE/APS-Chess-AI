import React from 'react';
import { Maximize2, Minimize2 } from 'lucide-react';

interface HeaderProps {
  onOpenArchitecture?: () => void;
  onOpenBenchmark?: () => void;
  depth: number;
  isThinking: boolean;
  gameStarted?: boolean;
  isOver?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  depth,
  isThinking,
  gameStarted = false,
  isOver = false,
}) => {
  const [isFullscreen, setIsFullscreen] = React.useState(false);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  };

  return (
    <header
      className="header-bar"
      style={{
        height: '44px',
        minHeight: '44px',
        maxHeight: '44px',
        padding: '0 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'var(--surface-chassis)',
        borderBottom: '1px solid var(--surface-border)',
        zIndex: 50,
      }}
    >
      {/* Brand & Project Identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {/* Dominant APS Institutional Brand */}
        <img
          src="/aps_white.png"
          alt="Applied Physics Society Logo"
          style={{ height: '24px', width: 'auto', objectFit: 'contain' }}
        />

        {/* Architectural Divider */}
        <div
          style={{
            width: '1px',
            height: '18px',
            background: 'var(--surface-border-strong)',
          }}
        />

        {/* Machine Learning Project Identity */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <img
            src="/ml_logo.png"
            alt="APS Machine Learning Team Logo"
            style={{
              height: '19px',
              width: 'auto',
              objectFit: 'contain',
            }}
          />
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: '13px',
                fontWeight: 700,
                letterSpacing: '0.04em',
                color: '#ffffff',
                textTransform: 'uppercase',
              }}
            >
              Chess AI
            </span>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
                color: 'var(--text-muted)',
                letterSpacing: '0.02em',
              }}
            >
              by APS Machine Learning Team
            </span>
          </div>
        </div>
      </div>

      {/* Stand Status & Display Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        {/* Live Engine Status Indicator */}
        <div
          id="header-status-pill"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'var(--surface-channel)',
            padding: '3px 10px',
            borderRadius: 'var(--radius-xs)',
            border: '1px solid var(--surface-border-subtle)',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
          }}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: isThinking ? 'var(--aps-red)' : isOver ? '#64748b' : 'var(--status-ready)',
              boxShadow: isThinking ? '0 0 6px rgba(171,24,24,0.6)' : isOver ? 'none' : '0 0 6px rgba(52,211,153,0.5)',
              transition: 'all 0.2s ease',
            }}
          />
          <span
            style={{
              color: isThinking ? '#fca5a5' : isOver ? '#94a3b8' : '#34d399',
              fontWeight: 600,
              letterSpacing: '0.03em',
            }}
          >
            {isThinking ? 'AI THINKING' : isOver ? 'GAME OVER' : !gameStarted ? 'READY' : 'ACTIVE'}
          </span>
          <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>· D{depth}</span>
        </div>

        {/* Fullscreen Toggle for Exhibition Stand */}
        <button
          onClick={toggleFullscreen}
          className="aps-btn aps-btn-secondary"
          style={{ height: '28px', width: '28px', padding: 0 }}
          title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Exhibition Mode'}
        >
          {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
        </button>
      </div>
    </header>
  );
};
