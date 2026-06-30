import React from 'react';
import { AbsoluteFill, Audio, Sequence, useVideoConfig } from 'remotion';
import { SignalChainSegment } from './SignalChainSegment';
import { MetadataOverlay } from './MetadataOverlay';
import { SlideTransition } from './SlideTransition';

interface GearItem extends Record<string, unknown> {
  name: string;
  imageUrl?: string;
  type: string;
}

interface ChainSegment extends Record<string, unknown> {
  chainName: string;
  gearItems: GearItem[];
  audioUrl: string;
  durationInFrames: number;
}

interface ShootoutVideoProps extends Record<string, unknown> {
  title: string;
  date?: string;
  attribution?: string;
  segments: ChainSegment[];
}

export const ShootoutVideo: React.FC<ShootoutVideoProps> = ({
  title,
  date,
  attribution,
  segments,
}) => {
  const { fps } = useVideoConfig();
  const transitionDuration = Math.floor(fps * 0.5); // 0.5 second transition

  let currentFrame = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: '#0a0a0a' }}>
      {/* Render each segment with audio and transitions */}
      {segments.map((segment, index) => {
        const segmentStart = currentFrame;
        const segmentDuration = segment.durationInFrames;

        // Update currentFrame for next segment
        currentFrame += segmentDuration;

        return (
          <React.Fragment key={index}>
            {/* Audio for this segment */}
            <Sequence from={segmentStart} durationInFrames={segmentDuration}>
              <Audio src={segment.audioUrl} />
            </Sequence>

            {/* Visual content with slide transition */}
            <Sequence from={segmentStart} durationInFrames={segmentDuration}>
              <SlideTransition
                direction="left"
                durationInFrames={transitionDuration}
              >
                <SignalChainSegment
                  chainName={segment.chainName}
                  gearItems={segment.gearItems}
                />
              </SlideTransition>
            </Sequence>
          </React.Fragment>
        );
      })}

      {/* Metadata overlay at the bottom */}
      <MetadataOverlay
        title={title}
        date={date}
        attribution={attribution}
        position="bottom"
      />
    </AbsoluteFill>
  );
};
