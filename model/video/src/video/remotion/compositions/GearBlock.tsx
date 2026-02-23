import React from 'react';

interface GearBlockProps {
  name: string;
  imageUrl?: string;
  type: string;
}

export const GearBlock: React.FC<GearBlockProps> = ({ name, imageUrl, type }) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '20px',
        backgroundColor: '#1a1a1a',
        borderRadius: '8px',
        minWidth: '200px',
      }}
    >
      {imageUrl && (
        <img
          src={imageUrl}
          alt={name}
          style={{
            width: '150px',
            height: '150px',
            objectFit: 'cover',
            borderRadius: '4px',
            marginBottom: '12px',
          }}
        />
      )}
      <div
        style={{
          fontSize: '18px',
          fontWeight: 'bold',
          color: '#ffffff',
          marginBottom: '8px',
          textAlign: 'center',
        }}
      >
        {name}
      </div>
      <div
        style={{
          fontSize: '12px',
          color: '#888888',
          backgroundColor: '#333333',
          padding: '4px 8px',
          borderRadius: '4px',
          textTransform: 'uppercase',
        }}
      >
        {type}
      </div>
    </div>
  );
};
