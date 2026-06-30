import React from 'react';
import { Composition } from 'remotion';
import { ShootoutVideo } from './compositions/ShootoutVideo';

// Default props for the ShootoutVideo composition
const defaultProps = {
  title: 'Guitar Tone Shootout',
  date: new Date().toISOString().split('T')[0],
  attribution: 'Created with Guitar Tone Shootout',
  segments: [
    {
      chainName: 'Clean Tone',
      gearItems: [
        { name: 'Stratocaster', type: 'Guitar' },
        { name: 'Fender Twin', type: 'Amp' },
      ],
      audioUrl: 'https://example.com/audio1.mp3',
      durationInFrames: 150,
    },
    {
      chainName: 'Overdriven',
      gearItems: [
        { name: 'Les Paul', type: 'Guitar' },
        { name: 'Tube Screamer', type: 'Pedal' },
        { name: 'Marshall JCM800', type: 'Amp' },
      ],
      audioUrl: 'https://example.com/audio2.mp3',
      durationInFrames: 150,
    },
  ],
};

const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="ShootoutVideo"
        component={ShootoutVideo}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={defaultProps}
      />
    </>
  );
};

export default Root;
