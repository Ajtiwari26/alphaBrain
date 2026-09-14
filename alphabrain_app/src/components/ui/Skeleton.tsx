import React from 'react';

export interface SkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  className = '',
  width,
  height,
}) => {
  return (
    <div
      className={`animate-shimmer bg-neutral-200/80 rounded ${className}`}
      style={{
        width: width !== undefined ? width : undefined,
        height: height !== undefined ? height : undefined,
      }}
    />
  );
};

export const SkeletonText: React.FC<{ lines?: number; className?: string }> = ({
  lines = 2,
  className = '',
}) => {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={`h-3 ${i === lines - 1 && lines > 1 ? 'w-4/5' : 'w-full'}`}
        />
      ))}
    </div>
  );
};

export const SkeletonRow: React.FC<{ className?: string }> = ({
  className = '',
}) => {
  return (
    <div className={`py-4 px-1 flex items-center justify-between gap-3 ${className}`}>
      <div className="flex-1 min-w-0 space-y-2">
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-2.5 w-3/4" />
      </div>
      <Skeleton className="w-4 h-4 rounded-full shrink-0" />
    </div>
  );
};

export const SkeletonCard: React.FC<{ className?: string }> = ({
  className = '',
}) => {
  return (
    <div className={`border border-[#0A0A0A] p-4 my-3 bg-zinc-50 space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-1/3" />
        <Skeleton className="h-3 w-16" />
      </div>
      <Skeleton className="h-6 w-3/4" />
      <div className="grid grid-cols-2 gap-3 pt-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    </div>
  );
};

export const SkeletonList: React.FC<{ rows?: number; className?: string }> = ({
  rows = 4,
  className = '',
}) => {
  return (
    <div className={`divide-y divide-[#0A0A0A] ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} />
      ))}
    </div>
  );
};

export default Skeleton;
