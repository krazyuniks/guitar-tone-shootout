/**
 * RemotionPlayer - Wrapper component for @remotion/player
 *
 * This component integrates the Remotion Player to render video compositions
 * in the browser as client-side React islands.
 *
 * Usage:
 *   <RemotionPlayer
 *     component={HeroAnimation}
 *     durationInFrames={150}
 *     compositionWidth={1920}
 *     compositionHeight={1080}
 *     fps={30}
 *     controls
 *     style={{ width: '100%' }}
 *   />
 */
import React from 'react';
import { Player, type PlayerRef } from '@remotion/player';

export interface RemotionPlayerProps {
  /** The Remotion composition component to render */
  component: React.ComponentType<any>;
  /** Duration of the composition in frames */
  durationInFrames: number;
  /** Width of the composition canvas */
  compositionWidth: number;
  /** Height of the composition canvas */
  compositionHeight: number;
  /** Frames per second */
  fps: number;
  /** Input props to pass to the composition */
  inputProps?: Record<string, any>;
  /** Show player controls */
  controls?: boolean;
  /** Autoplay the composition */
  autoPlay?: boolean;
  /** Loop the composition */
  loop?: boolean;
  /** Additional CSS class names */
  className?: string;
  /** Inline styles */
  style?: React.CSSProperties;
  /** Test ID for Playwright testing */
  'data-testid'?: string;
}

/**
 * RemotionPlayer component wraps @remotion/player for client-side video rendering.
 */
export const RemotionPlayer: React.FC<RemotionPlayerProps> = ({
  component,
  durationInFrames,
  compositionWidth,
  compositionHeight,
  fps,
  inputProps = {},
  controls = false,
  autoPlay = false,
  loop = false,
  className = '',
  style = {},
  'data-testid': testId,
}) => {
  const playerRef = React.useRef<PlayerRef>(null);

  return (
    <div className={className} style={style} data-testid={testId}>
      <Player
        ref={playerRef}
        component={component}
        durationInFrames={durationInFrames}
        compositionWidth={compositionWidth}
        compositionHeight={compositionHeight}
        fps={fps}
        inputProps={inputProps}
        controls={controls}
        autoPlay={autoPlay}
        loop={loop}
        style={{ width: '100%' }}
      />
    </div>
  );
};

export default RemotionPlayer;
