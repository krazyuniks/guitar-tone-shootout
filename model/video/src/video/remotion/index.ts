import { registerRoot } from 'remotion';
import Root from './Root';

registerRoot(Root);

export { default as Root } from './Root';
export { ShootoutVideo } from './compositions/ShootoutVideo';
export { GearBlock } from './compositions/GearBlock';
export { SignalChainSegment } from './compositions/SignalChainSegment';
export { SlideTransition } from './compositions/SlideTransition';
export { MetadataOverlay } from './compositions/MetadataOverlay';
