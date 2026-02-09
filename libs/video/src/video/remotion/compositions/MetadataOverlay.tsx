import React from 'react';

interface MetadataOverlayProps {
  title: string;
  date?: string;
  attribution?: string;
  position?: 'top' | 'bottom';
}

export const MetadataOverlay: React.FC<MetadataOverlayProps> = ({
  title,
  date,
  attribution,
  position = 'bottom',
}) => {
  const positionStyles =
    position === 'top'
      ? { top: 0, paddingTop: '20px' }
      : { bottom: 0, paddingBottom: '20px' };

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        ...positionStyles,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '8px',
      }}
    >
      <div
        style={{
          fontSize: '24px',
          fontWeight: 'bold',
          color: '#ffffff',
          textAlign: 'center',
        }}
      >
        {title}
      </div>
      {date && (
        <div
          style={{
            fontSize: '14px',
            color: '#aaaaaa',
            textAlign: 'center',
          }}
        >
          {date}
        </div>
      )}
      {attribution && (
        <div
          style={{
            fontSize: '12px',
            color: '#888888',
            textAlign: 'center',
          }}
        >
          {attribution}
        </div>
      )}
    </div>
  );
};
