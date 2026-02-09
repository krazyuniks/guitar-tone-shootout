import React from 'react';
import { GearBlock } from './GearBlock';

interface GearItem {
  name: string;
  imageUrl?: string;
  type: string;
}

interface SignalChainSegmentProps {
  chainName: string;
  gearItems: GearItem[];
}

export const SignalChainSegment: React.FC<SignalChainSegmentProps> = ({
  chainName,
  gearItems,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        backgroundColor: '#0a0a0a',
        padding: '40px',
      }}
    >
      <div
        style={{
          fontSize: '32px',
          fontWeight: 'bold',
          color: '#ffffff',
          marginBottom: '30px',
          textAlign: 'center',
        }}
      >
        {chainName}
      </div>
      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '20px',
          flexWrap: 'wrap',
        }}
      >
        {gearItems.map((gear, index) => (
          <React.Fragment key={index}>
            <GearBlock name={gear.name} imageUrl={gear.imageUrl} type={gear.type} />
            {index < gearItems.length - 1 && (
              <div
                style={{
                  fontSize: '24px',
                  color: '#666666',
                }}
              >
                →
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
