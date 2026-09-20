import React, { useState, useMemo } from 'react';
import { Chess } from 'chess.js';
import { Square } from './Square';
import { Piece } from './Piece';
import { EvaluationBar } from './EvaluationBar';
import { PromotionModal } from './PromotionModal';
import type { MoveResult } from '../../types';

interface ChessboardProps {
  fen: string;
  orientation: 'white' | 'black';
  evaluation?: number | null;
  legalMoves: string[];
  lastMove: MoveResult | null;
  isCheck: boolean;
  turn: 'white' | 'black';
  humanColor: 'white' | 'black';
  isThinking: boolean;
  onMakeMove: (uci: string) => void;
}

export const Chessboard: React.FC<ChessboardProps> = ({
  fen,
  orientation,
  evaluation = 0.0,
  legalMoves,
  lastMove,
  isCheck,
  turn,
  humanColor,
  isThinking,
  onMakeMove,
}) => {
  const [selectedSquare, setSelectedSquare] = useState<string | null>(null);
  const [pendingPromotion, setPendingPromotion] = useState<{ from: string; to: string } | null>(null);

  // Client-side chess instance purely for reading piece placements and legality previews
  const chess = useMemo(() => {
    try {
      return new Chess(fen);
    } catch {
      return new Chess();
    }
  }, [fen]);

  // Compute 8x8 grid layout based on orientation
  const ranks = orientation === 'white' ? [8, 7, 6, 5, 4, 3, 2, 1] : [1, 2, 3, 4, 5, 6, 7, 8];
  const files = orientation === 'white' ? ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] : ['h', 'g', 'f', 'e', 'd', 'c', 'b', 'a'];

  // Find King square if in check
  const inCheckKingSquare = useMemo(() => {
    if (!isCheck) return null;
    const currentTurn = chess.turn();
    const board = chess.board();
    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        const piece = board[r][c];
        if (piece && piece.type === 'k' && piece.color === currentTurn) {
          const file = String.fromCharCode('a'.charCodeAt(0) + c);
          const rank = 8 - r;
          return `${file}${rank}`;
        }
      }
    }
    return null;
  }, [chess, isCheck]);

  // Extract last move from/to squares
  const lastMoveSquares = useMemo(() => {
    if (!lastMove || !lastMove.uci || lastMove.uci.length < 4) return [];
    return [lastMove.uci.slice(0, 2), lastMove.uci.slice(2, 4)];
  }, [lastMove]);

  // Available target squares for the currently selected square
  const legalTargetsForSelected = useMemo(() => {
    if (!selectedSquare) return new Set<string>();
    const targets = new Set<string>();
    for (const uci of legalMoves) {
      if (uci.startsWith(selectedSquare)) {
        targets.add(uci.slice(2, 4));
      }
    }
    return targets;
  }, [selectedSquare, legalMoves]);

  const handleMoveAttempt = (from: string, to: string) => {
    if (from === to) {
      setSelectedSquare(null);
      return;
    }

    const piece = chess.get(from as any);
    if (!piece) return;

    // Check for pawn promotion
    const isPawn = piece.type === 'p';
    const isPromotingWhite = isPawn && piece.color === 'w' && from[1] === '7' && to[1] === '8';
    const isPromotingBlack = isPawn && piece.color === 'b' && from[1] === '2' && to[1] === '1';

    if (isPromotingWhite || isPromotingBlack) {
      // Check if move is legal with default queen promotion
      if (legalMoves.includes(`${from}${to}q`)) {
        setPendingPromotion({ from, to });
        return;
      }
    }

    // Normal move
    const uci = `${from}${to}`;
    if (legalMoves.includes(uci)) {
      setSelectedSquare(null);
      onMakeMove(uci);
    } else {
      setSelectedSquare(null);
    }
  };

  const handleSquareClick = (square: string) => {
    if (isThinking || turn !== humanColor) {
      return;
    }

    const clickedPiece = chess.get(square as any);

    // If already have a selected square
    if (selectedSquare) {
      if (legalTargetsForSelected.has(square)) {
        handleMoveAttempt(selectedSquare, square);
        return;
      }

      // If clicking own piece, switch selection
      if (clickedPiece && ((clickedPiece.color === 'w' && humanColor === 'white') || (clickedPiece.color === 'b' && humanColor === 'black'))) {
        setSelectedSquare(square);
        return;
      }

      // Deselect
      setSelectedSquare(null);
    } else {
      // Select if human's own piece
      if (clickedPiece && ((clickedPiece.color === 'w' && humanColor === 'white') || (clickedPiece.color === 'b' && humanColor === 'black'))) {
        setSelectedSquare(square);
      }
    }
  };

  const handleDragStart = (e: React.DragEvent, square: string) => {
    if (isThinking || turn !== humanColor) {
      e.preventDefault();
      return;
    }
    const piece = chess.get(square as any);
    if (!piece || (piece.color === 'w' && humanColor !== 'white') || (piece.color === 'b' && humanColor !== 'black')) {
      e.preventDefault();
      return;
    }

    setSelectedSquare(square);
    e.dataTransfer.setData('text/plain', square);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDrop = (targetSquare: string) => {
    if (!selectedSquare) return;
    if (legalTargetsForSelected.has(targetSquare)) {
      handleMoveAttempt(selectedSquare, targetSquare);
    }
  };

  return (
    <div className="board-chassis">
      {/* Precision Integrated Evaluation Gauge Channel */}
      <EvaluationBar evaluation={evaluation} orientation={orientation} />

      {/* 8x8 Chessboard Grid */}
      <div className="board-grid">
        {ranks.map((rank, rankIdx) =>
          files.map((file, fileIdx) => {
            const sq = `${file}${rank}`;
            const isLight = (file.charCodeAt(0) - 'a'.charCodeAt(0) + rank) % 2 !== 0;
            const piece = chess.get(sq as any);
            const pieceCode = piece ? `${piece.color}${piece.type.toUpperCase()}` : null;

            const isSelected = selectedSquare === sq;
            const isLastMoveSq = lastMoveSquares.includes(sq);
            const isCheckSq = inCheckKingSquare === sq;
            const isLegalTarget = legalTargetsForSelected.has(sq);
            const hasPieceToCapture = isLegalTarget && piece !== null;

            const rankLabel = fileIdx === 0 ? String(rank) : null;
            const fileLabel = rankIdx === 7 ? file : null;

            return (
              <Square
                key={sq}
                square={sq}
                isLight={isLight}
                isSelected={isSelected}
                isLastMove={isLastMoveSq}
                isCheck={isCheckSq}
                isLegalTarget={isLegalTarget}
                hasPieceToCapture={hasPieceToCapture}
                rankLabel={rankLabel}
                fileLabel={fileLabel}
                onClick={() => handleSquareClick(sq)}
                onDrop={() => handleDrop(sq)}
                onDragOver={(e) => {
                  if (legalTargetsForSelected.has(sq)) {
                    e.preventDefault();
                  }
                }}
              >
                {pieceCode && (
                  <div
                    draggable={!isThinking && turn === humanColor && ((piece?.color === 'w' && humanColor === 'white') || (piece?.color === 'b' && humanColor === 'black'))}
                    onDragStart={(e) => handleDragStart(e, sq)}
                    style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  >
                    <Piece piece={pieceCode} />
                  </div>
                )}
              </Square>
            );
          })
        )}
      </div>

      {/* Pawn Promotion Modal */}
      {pendingPromotion && (
        <PromotionModal
          color={humanColor}
          onSelect={(pieceType) => {
            const uci = `${pendingPromotion.from}${pendingPromotion.to}${pieceType}`;
            setPendingPromotion(null);
            setSelectedSquare(null);
            onMakeMove(uci);
          }}
          onCancel={() => {
            setPendingPromotion(null);
            setSelectedSquare(null);
          }}
        />
      )}
    </div>
  );
};
