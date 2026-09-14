import React from 'react';

export interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  color?: string;
  className?: string;
  label?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  color = '#E6391E',
  className = '',
  label,
}) => {
  const sizeMap = {
    sm: 'w-3.5 h-3.5 border-2',
    md: 'w-5 h-5 border-2',
    lg: 'w-8 h-8 border-[3px]',
    xl: 'w-12 h-12 border-4',
  };

  return (
    <div className={`inline-flex items-center gap-2.5 ${className}`} role="status" aria-label={label || 'Loading'}>
      <div
        className={`${sizeMap[size]} rounded-full border-neutral-200 border-t-transparent animate-spin-smooth`}
        style={{ borderTopColor: color }}
      />
      {label && (
        <span className="font-mono text-xs text-neutral-500 uppercase tracking-wider animate-pulse">
          {label}
        </span>
      )}
    </div>
  );
};

export default LoadingSpinner;
