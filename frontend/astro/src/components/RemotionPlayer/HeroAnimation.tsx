/**
 * HeroAnimation - Animated hero section composition for homepage
 *
 * This is a Remotion composition that renders an animated hero section
 * showcasing the Guitar Tone Shootout brand and value proposition.
 *
 * Rendered client-side using @remotion/player as a React island.
 */
import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

export interface HeroAnimationProps {
  /** Main title text */
  title?: string;
  /** Subtitle text */
  subtitle?: string;
  /** Background color */
  backgroundColor?: string;
  /** Text color */
  textColor?: string;
}

/**
 * HeroAnimation composition component
 */
export const HeroAnimation: React.FC<HeroAnimationProps> = ({
  title = 'Guitar Tone Shootout',
  subtitle = 'Compare. Listen. Decide.',
  backgroundColor = '#0a0a0a',
  textColor = '#ffffff',
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Title slide-in animation (frames 0-30)
  const titleProgress = spring({
    frame: frame - 0,
    fps,
    config: {
      damping: 100,
      stiffness: 200,
      mass: 0.5,
    },
  });

  const titleOpacity = interpolate(titleProgress, [0, 1], [0, 1]);
  const titleTranslateY = interpolate(titleProgress, [0, 1], [50, 0]);

  // Subtitle slide-in animation (frames 15-45)
  const subtitleProgress = spring({
    frame: frame - 15,
    fps,
    config: {
      damping: 100,
      stiffness: 200,
      mass: 0.5,
    },
  });

  const subtitleOpacity = interpolate(subtitleProgress, [0, 1], [0, 1]);
  const subtitleTranslateY = interpolate(subtitleProgress, [0, 1], [30, 0]);

  // Pulse animation for subtitle (after frame 60)
  const pulseFrame = Math.max(0, frame - 60);
  const pulse = Math.sin((pulseFrame / fps) * Math.PI * 2) * 0.1 + 1;

  return (
    <AbsoluteFill
      style={{
        backgroundColor,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      {/* Title */}
      <div
        style={{
          fontSize: 80,
          fontWeight: 'bold',
          color: textColor,
          opacity: titleOpacity,
          transform: `translateY(${titleTranslateY}px)`,
          marginBottom: 20,
          textAlign: 'center',
        }}
      >
        {title}
      </div>

      {/* Subtitle */}
      <div
        style={{
          fontSize: 40,
          color: textColor,
          opacity: subtitleOpacity * 0.8,
          transform: `translateY(${subtitleTranslateY}px) scale(${pulse})`,
          textAlign: 'center',
        }}
      >
        {subtitle}
      </div>

      {/* Accent line */}
      <div
        style={{
          width: interpolate(titleProgress, [0, 1], [0, 400]),
          height: 4,
          backgroundColor: textColor,
          marginTop: 40,
          opacity: titleOpacity,
        }}
      />
    </AbsoluteFill>
  );
};

export default HeroAnimation;
