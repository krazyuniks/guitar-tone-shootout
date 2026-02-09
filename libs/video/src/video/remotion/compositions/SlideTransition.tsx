import React from 'react';
import { interpolate, useCurrentFrame } from 'remotion';

interface SlideTransitionProps {
  children: React.ReactNode;
  direction?: 'left' | 'right' | 'up' | 'down';
  durationInFrames: number;
}

export const SlideTransition: React.FC<SlideTransitionProps> = ({
  children,
  direction = 'left',
  durationInFrames,
}) => {
  const frame = useCurrentFrame();

  // Interpolate position based on frame
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // Calculate transform based on direction
  let transform = '';
  switch (direction) {
    case 'left':
      transform = `translateX(${(1 - progress) * -100}%)`;
      break;
    case 'right':
      transform = `translateX(${(1 - progress) * 100}%)`;
      break;
    case 'up':
      transform = `translateY(${(1 - progress) * -100}%)`;
      break;
    case 'down':
      transform = `translateY(${(1 - progress) * 100}%)`;
      break;
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        transform,
        transition: 'transform 0.3s ease-out',
      }}
    >
      {children}
    </div>
  );
};
