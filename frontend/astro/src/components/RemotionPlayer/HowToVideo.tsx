/**
 * HowToVideo - Instructional video composition explaining how to use GTS
 *
 * This is a Remotion composition that renders an animated how-to video
 * explaining the key features and workflow of Guitar Tone Shootout.
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

export interface HowToVideoProps {
  /** Steps to display in the how-to video */
  steps?: Array<{
    title: string;
    description: string;
    icon?: string;
  }>;
  /** Background color */
  backgroundColor?: string;
  /** Text color */
  textColor?: string;
  /** Accent color */
  accentColor?: string;
}

const defaultSteps = [
  {
    title: '1. Build Your Chain',
    description: 'Select gear and create your signal chain',
    icon: '🎸',
  },
  {
    title: '2. Record Audio',
    description: 'Upload or record your guitar performance',
    icon: '🎵',
  },
  {
    title: '3. Compare Tones',
    description: 'Listen to different gear combinations side-by-side',
    icon: '🎧',
  },
  {
    title: '4. Share Results',
    description: 'Export and share your tone shootout',
    icon: '📤',
  },
];

/**
 * HowToVideo composition component
 */
export const HowToVideo: React.FC<HowToVideoProps> = ({
  steps = defaultSteps,
  backgroundColor = '#1a1a1a',
  textColor = '#ffffff',
  accentColor = '#3b82f6',
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Calculate frames per step
  const framesPerStep = Math.floor(durationInFrames / steps.length);

  // Determine current step based on frame
  const currentStepIndex = Math.min(
    Math.floor(frame / framesPerStep),
    steps.length - 1
  );
  const currentStep = steps[currentStepIndex];

  // Frame within current step
  const stepFrame = frame % framesPerStep;

  // Step transition animation
  const stepProgress = spring({
    frame: stepFrame,
    fps,
    config: {
      damping: 100,
      stiffness: 200,
      mass: 0.5,
    },
  });

  const stepOpacity = interpolate(stepProgress, [0, 1], [0, 1]);
  const stepScale = interpolate(stepProgress, [0, 1], [0.8, 1]);
  const stepTranslateY = interpolate(stepProgress, [0, 1], [40, 0]);

  // Icon rotation animation
  const iconRotation = interpolate(
    stepProgress,
    [0, 1],
    [0, 360],
    {
      extrapolateRight: 'clamp',
    }
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 80,
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      {/* Header */}
      <div
        style={{
          position: 'absolute',
          top: 60,
          fontSize: 48,
          fontWeight: 'bold',
          color: accentColor,
        }}
      >
        How to Use Guitar Tone Shootout
      </div>

      {/* Step indicator */}
      <div
        style={{
          position: 'absolute',
          top: 140,
          fontSize: 24,
          color: textColor,
          opacity: 0.6,
        }}
      >
        Step {currentStepIndex + 1} of {steps.length}
      </div>

      {/* Current step content */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          opacity: stepOpacity,
          transform: `scale(${stepScale}) translateY(${stepTranslateY}px)`,
        }}
      >
        {/* Icon */}
        {currentStep.icon && (
          <div
            style={{
              fontSize: 120,
              marginBottom: 40,
              transform: `rotate(${iconRotation}deg)`,
            }}
          >
            {currentStep.icon}
          </div>
        )}

        {/* Title */}
        <div
          style={{
            fontSize: 64,
            fontWeight: 'bold',
            color: textColor,
            marginBottom: 20,
            textAlign: 'center',
          }}
        >
          {currentStep.title}
        </div>

        {/* Description */}
        <div
          style={{
            fontSize: 36,
            color: textColor,
            opacity: 0.8,
            textAlign: 'center',
            maxWidth: 800,
          }}
        >
          {currentStep.description}
        </div>
      </div>

      {/* Progress bar */}
      <div
        style={{
          position: 'absolute',
          bottom: 60,
          width: '80%',
          height: 8,
          backgroundColor: 'rgba(255, 255, 255, 0.1)',
          borderRadius: 4,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${((currentStepIndex + stepProgress) / steps.length) * 100}%`,
            height: '100%',
            backgroundColor: accentColor,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

export default HowToVideo;
