import React from 'react';

interface ThinkingOrbitProps {
  isThinking: boolean;
  size?: number;
}

export const ThinkingOrbit: React.FC<ThinkingOrbitProps> = ({ isThinking, size = 44 }) => {
  return (
    <div
      className="orbit-container"
      style={{
        width: `${size}px`,
        height: `${size}px`,
        opacity: isThinking ? 1 : 0.6,
        transition: 'opacity 0.3s ease',
      }}
      title={isThinking ? "AI is calculating search tree..." : "AI Engine Idle"}
    >
      <div
        className="orbit-ring orbit-ring-1"
        style={{
          animationPlayState: isThinking ? 'running' : 'paused',
        }}
      />
      <div
        className="orbit-ring orbit-ring-2"
        style={{
          animationPlayState: isThinking ? 'running' : 'paused',
        }}
      />
      <div
        className="orbit-ring orbit-ring-3"
        style={{
          animationPlayState: isThinking ? 'running' : 'paused',
        }}
      />
      <div
        className="orbit-nucleus"
        style={{
          width: `${Math.max(8, Math.round(size * 0.28))}px`,
          height: `${Math.max(8, Math.round(size * 0.28))}px`,
          animationPlayState: isThinking ? 'running' : 'paused',
        }}
      />
    </div>
  );
};
