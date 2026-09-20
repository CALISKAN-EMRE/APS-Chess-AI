import React from 'react';
import { X, Layers, Cpu, Database, Binary, GitBranch, ArrowRight } from 'lucide-react';

interface ArchitectureViewProps {
  onClose: () => void;
}

export const ArchitectureView: React.FC<ArchitectureViewProps> = ({ onClose }) => {
  const stages = [
    {
      step: 1,
      title: 'Board Spatial Tensor',
      icon: Layers,
      spec: '8 × 8 × 12 Tensor (Float32)',
      details:
        'Converts chess board into 12 binary channels: 6 piece types for White (P, N, B, R, Q, K) and 6 for Black. Preserves exact spatial rank/file orientation without lossy board representations.',
    },
    {
      step: 2,
      title: 'Deep Value Network',
      icon: Cpu,
      spec: 'Keras v3 Deep CNN Architecture',
      details:
        'Evaluated via a compiled TensorFlow graph. Directly evaluates static board positions into continuous scalar scores in [-1.0, +1.0]. Explicit terminal checkmate scoring (±10.0) is handled cleanly in the search algorithm.',
    },
    {
      step: 3,
      title: 'Iterative Deepening',
      icon: GitBranch,
      spec: 'Progressive Search (D1 → D2 → D3)',
      details:
        'Searches depth 1 first to establish high-quality root move ordering. Seeds candidate moves into subsequent depths to maximize early alpha-beta branch pruning and minimize search latency.',
    },
    {
      step: 4,
      title: 'Transposition Table (TT)',
      icon: Database,
      spec: 'Bounded Cache (EXACT / LOWER / UPPER)',
      details:
        'Stores position hash entries with search depth, evaluated bounds, and cutoff best moves. Prevents redundant evaluations of identical transpositions across iterative search trees.',
    },
    {
      step: 5,
      title: 'Principal Variation Search',
      icon: Binary,
      spec: 'Scout Narrow Windows [α, α + ε]',
      details:
        'Evaluates the first ordered move with a full alpha-beta window. All subsequent candidate moves are tested with a narrow null-window scout search, re-searching only when a candidate proves superior.',
    },
    {
      step: 6,
      title: 'Decision & Move Selection',
      icon: ArrowRight,
      spec: 'Deterministic Root Tie-Breaking',
      details:
        'Selects the optimal move deterministically according to established root move ordering. Ensures 100% reproducible engine behavior with zero random drift across game sessions.',
    },
  ];

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
              Applied Physics Society · Technical Architecture
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
              Engine Architecture & Search Pipeline
            </h2>
          </div>
          <button
            id="close-architecture-btn"
            onClick={onClose}
            className="aps-btn aps-btn-secondary"
            style={{ padding: '6px 10px' }}
            title="Close modal"
          >
            <X size={16} />
          </button>
        </div>

        {/* Pipeline Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {stages.map((st) => {
            const Icon = st.icon;
            return (
              <div
                key={st.step}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '18px',
                  padding: '16px 20px',
                  background: 'var(--surface-elevated)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--surface-border-subtle)',
                }}
              >
                <div
                  style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--status-computing-bg)',
                    border: '1px solid var(--status-computing-border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginTop: '2px',
                  }}
                >
                  <Icon size={19} color="var(--aps-red)" />
                </div>

                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '6px',
                      flexWrap: 'wrap',
                      gap: '8px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '12px',
                          color: 'var(--aps-red)',
                          fontWeight: 700,
                        }}
                      >
                        0{st.step}.
                      </span>
                      <h4
                        className="font-display"
                        style={{ fontSize: '15px', fontWeight: 600, color: '#ffffff' }}
                      >
                        {st.title}
                      </h4>
                    </div>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '11px',
                        background: 'var(--surface-channel)',
                        padding: '3px 10px',
                        borderRadius: 'var(--radius-xs)',
                        border: '1px solid var(--surface-border)',
                        color: 'var(--text-secondary)',
                        fontWeight: 500,
                      }}
                    >
                      {st.spec}
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: '13.5px',
                      color: 'var(--text-secondary)',
                      lineHeight: 1.6,
                    }}
                  >
                    {st.details}
                  </p>
                </div>
              </div>
            );
          })}
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
              Engine designed & trained by the <strong style={{ color: '#ffffff' }}>APS Machine Learning Team</strong>
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
