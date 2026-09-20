import React from 'react';
import { X, CheckCircle2, ShieldCheck, Target, Award, AlertTriangle } from 'lucide-react';

interface BenchmarkViewProps {
  onClose: () => void;
}

export const BenchmarkView: React.FC<BenchmarkViewProps> = ({ onClose }) => {
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer-modal custom-scroll" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--surface-border)',
            paddingBottom: '14px',
          }}
        >
          <div>
            <span
              style={{
                fontSize: '11px',
                fontFamily: 'var(--font-mono)',
                color: 'var(--aps-red)',
                textTransform: 'uppercase',
                fontWeight: 700,
                letterSpacing: '0.06em',
              }}
            >
              External Reference Validation
            </span>
            <h2
              className="font-display"
              style={{
                fontSize: '22px',
                fontWeight: 700,
                color: '#ffffff',
                letterSpacing: '0.01em',
                marginTop: '2px',
              }}
            >
              Stockfish 19 Move-Quality Benchmark
            </h2>
          </div>
          <button
            id="close-benchmark-btn"
            onClick={onClose}
            className="aps-btn aps-btn-secondary"
            style={{ padding: '6px 10px' }}
            title="Close modal"
          >
            <X size={16} />
          </button>
        </div>

        {/* Disclaimer Alert */}
        <div
          style={{
            padding: '14px 18px',
            background: 'var(--status-computing-bg)',
            border: '1px solid var(--status-computing-border)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '14px',
          }}
        >
          <AlertTriangle size={18} color="var(--aps-red)" style={{ flexShrink: 0 }} />
          <p style={{ fontSize: '13px', color: '#fca5a5', lineHeight: 1.5 }}>
            <strong style={{ color: '#ffffff' }}>Objective External Benchmark:</strong> Stockfish 19 (evaluated at Search Depth 14) is utilized strictly as an external referee to quantify centipawn move accuracy. The project engine operates entirely on its own standalone neural value network.
          </p>
        </div>

        {/* Key Metrics Grid: Strong Emphasis on 3 Primary Figures */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
          <div
            style={{
              padding: '16px 18px',
              background: 'var(--surface-elevated)',
              border: '1px solid var(--surface-border)',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Target size={14} color="var(--aps-red)" />
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: 'var(--text-muted)',
                }}
              >
                Median CP Loss
              </span>
            </div>
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '28px',
                fontWeight: 700,
                color: '#ffffff',
                letterSpacing: '-0.02em',
              }}
            >
              69.5 <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>cp</span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Depth-2 evaluation baseline
            </span>
          </div>

          <div
            style={{
              padding: '16px 18px',
              background: 'var(--surface-elevated)',
              border: '1px solid var(--surface-border)',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Award size={14} color="var(--aps-red)" />
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: 'var(--text-muted)',
                }}
              >
                High-Quality Moves
              </span>
            </div>
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '28px',
                fontWeight: 700,
                color: '#34d399',
                letterSpacing: '-0.02em',
              }}
            >
              60.0%
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Within 100 cp of Stockfish choice
            </span>
          </div>

          <div
            style={{
              padding: '16px 18px',
              background: 'var(--surface-elevated)',
              border: '1px solid var(--surface-border)',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ShieldCheck size={14} color="var(--aps-red)" />
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: 'var(--text-muted)',
                }}
              >
                Acceptable Moves
              </span>
            </div>
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '28px',
                fontWeight: 700,
                color: '#60a5fa',
                letterSpacing: '-0.02em',
              }}
            >
              72.5%
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Within 200 cp of Stockfish choice
            </span>
          </div>
        </div>

        {/* 40-Position Regression Validation Card */}
        <div
          style={{
            padding: '18px 20px',
            background: 'var(--surface-elevated)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--surface-border)',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={17} color="#34d399" />
              <h4 className="font-display" style={{ fontSize: '15px', fontWeight: 600, color: '#ffffff' }}>
                40-Position Deterministic Regression Suite
              </h4>
            </div>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                fontWeight: 700,
                color: '#34d399',
                background: 'var(--status-ready-bg)',
                padding: '3px 9px',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--status-ready-border)',
              }}
            >
              100% PASS (0 MISMATCHES)
            </span>
          </div>
          <p style={{ fontSize: '13.5px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Validated across opening, tactical middlegames, endgames, and quiet positions for both White and Black to move. Principal Variation Search (PVS) with Transposition Table (TT) matched the unoptimized alpha-beta search on <strong style={{ color: '#ffffff' }}>40 out of 40 positions</strong> with identical best moves and evaluations.
          </p>
        </div>

        {/* Depth Scaling Comparison */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
          <div
            style={{
              padding: '16px 18px',
              background: 'var(--surface-elevated)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--surface-border)',
            }}
          >
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.04em' }}>
              DEPTH 2 SEARCH (STANDARD DEMO)
            </div>
            <div style={{ marginTop: '10px', fontSize: '13.5px', color: '#ffffff', display: 'flex', flexDirection: 'column', gap: '5px' }}>
              <div>Median Centipawn Loss: <strong style={{ color: '#ffffff' }}>69.5 cp</strong></div>
              <div>Average Centipawn Loss: <strong style={{ color: '#ffffff' }}>180.7 cp</strong></div>
              <div>Typical Move Time: <strong style={{ color: 'var(--text-secondary)' }}>~1.1s</strong></div>
            </div>
          </div>

          <div
            style={{
              padding: '16px 18px',
              background: 'var(--surface-elevated)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--surface-border)',
            }}
          >
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--aps-red)', fontWeight: 600, letterSpacing: '0.04em' }}>
              DEPTH 3 SEARCH (DEEP REASONING)
            </div>
            <div style={{ marginTop: '10px', fontSize: '13.5px', color: '#ffffff', display: 'flex', flexDirection: 'column', gap: '5px' }}>
              <div>Median Centipawn Loss: <strong style={{ color: '#34d399' }}>35.0 cp</strong> (50% reduction)</div>
              <div>Moves &le; 100 cp: <strong style={{ color: '#34d399' }}>75.0%</strong></div>
              <div>Typical Move Time: <strong style={{ color: 'var(--text-secondary)' }}>~5.4s</strong></div>
            </div>
          </div>
        </div>

        {/* Integrated Footer Attribution */}
        <div
          style={{
            padding: '14px 20px',
            background: 'var(--surface-channel)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--surface-border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            marginTop: '4px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <img
              src="/ml_logo.png"
              alt="APS Machine Learning Team"
              style={{ height: '22px', width: 'auto', objectFit: 'contain' }}
            />
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Evaluated against Stockfish 19 by the <strong style={{ color: '#ffffff' }}>APS Machine Learning Team</strong>
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                fontSize: '10px',
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-muted)',
                letterSpacing: '0.06em',
              }}
            >
              A PROJECT OF
            </span>
            <img
              src="/aps_white.png"
              alt="Applied Physics Society"
              style={{ height: '22px', width: 'auto', objectFit: 'contain' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
