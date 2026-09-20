import React from 'react';

interface EvaluationBarProps {
  evaluation: number | null;
  orientation: 'white' | 'black';
}

export const EvaluationBar: React.FC<EvaluationBarProps> = ({
  evaluation,
  orientation,
}) => {
  const evalValue = evaluation ?? 0.0;

  // Clamped [-10.0, +10.0] -> [5%, 95%]
  const clampedScore = Math.max(-10, Math.min(10, evalValue));
  const whitePercent = Math.round(50 + (clampedScore / 10) * 45);

  // If orientation is Black, invert the bar height
  const fillHeight = orientation === 'white' ? whitePercent : 100 - whitePercent;

  return (
    <div
      className="eval-gauge"
      title={`Evaluation: ${evalValue >= 0 ? '+' : ''}${evalValue.toFixed(2)} pts`}
    >
      <div className="eval-gauge-tick" title="Neutral 0.00" />
      <div
        className="eval-gauge-fill"
        style={{
          height: `${fillHeight}%`,
        }}
      />
    </div>
  );
};
