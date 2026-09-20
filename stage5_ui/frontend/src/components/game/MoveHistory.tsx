import React, { useRef, useEffect } from 'react';
import type { MoveHistoryItem } from '../../types';

interface MoveHistoryProps {
  history: MoveHistoryItem[];
}

export const MoveHistory: React.FC<MoveHistoryProps> = ({ history }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Group moves into pairs (White move, Black move)
  const movePairs: Array<{ number: number; white?: MoveHistoryItem; black?: MoveHistoryItem }> = [];
  for (let i = 0; i < history.length; i++) {
    const item = history[i];
    if (item.color === 'white') {
      movePairs.push({ number: item.move_number, white: item });
    } else {
      if (movePairs.length > 0 && movePairs[movePairs.length - 1].number === item.move_number) {
        movePairs[movePairs.length - 1].black = item;
      } else {
        movePairs.push({ number: item.move_number, black: item });
      }
    }
  }

  // Auto-scroll to bottom on new moves
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history.length]);

  return (
    <div id="panel-move-history" className="history-section panel-history">
      {/* Hairline Console Divider */}
      <div className="console-divider" />

      {/* Notation Header */}
      <div className="console-section-header">
        <span>Move History</span>
        <span>
          {history.length} {history.length === 1 ? 'PLY' : 'PLIES'}
        </span>
      </div>

      {/* Adaptive Notation Content */}
      <div ref={scrollRef} className="history-scroll custom-scroll">
        {movePairs.length === 0 ? (
          <div
            style={{
              padding: '10px 4px',
              color: 'var(--text-muted)',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              fontStyle: 'italic',
            }}
          >
            Awaiting opening ply — game ready.
          </div>
        ) : (
          <table className="history-table">
            <tbody>
              {movePairs.map((pair, idx) => {
                const isLastPair = idx === movePairs.length - 1;
                return (
                  <tr
                    key={pair.number}
                    className={isLastPair ? 'active-ply' : ''}
                  >
                    <td className="history-num">{pair.number}.</td>
                    <td
                      className="history-san"
                      style={{
                        fontWeight: isLastPair && !pair.black ? 700 : 500,
                        color: pair.white ? '#ffffff' : 'transparent',
                      }}
                    >
                      {pair.white ? pair.white.san : '-'}
                    </td>
                    <td
                      className="history-san"
                      style={{
                        fontWeight: isLastPair && pair.black ? 700 : 500,
                        color: pair.black ? '#ffffff' : 'transparent',
                      }}
                    >
                      {pair.black ? pair.black.san : ''}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
