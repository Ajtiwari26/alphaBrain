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

export const SkeletonRow: React.FC<{ cols?: number; className?: string }> = ({
  className = '',
}) => {
  return (
    <div className={`grid grid-cols-12 px-6 py-4 items-center gap-4 ${className}`}>
      <div className="col-span-4 flex items-center gap-3">
        <Skeleton className="w-8 h-8 rounded shrink-0" />
        <div className="space-y-1.5 flex-1">
          <Skeleton className="h-3.5 w-3/4" />
          <Skeleton className="h-2.5 w-1/2" />
        </div>
      </div>
      <div className="col-span-4">
        <Skeleton className="h-3 w-4/5" />
      </div>
      <div className="col-span-2">
        <Skeleton className="h-3 w-2/3" />
      </div>
      <div className="col-span-2 flex justify-end">
        <Skeleton className="h-5 w-16 rounded" />
      </div>
    </div>
  );
};

export const SkeletonCard: React.FC<{ className?: string }> = ({
  className = '',
}) => {
  return (
    <div className={`border border-[#0A0A0A] bg-white p-6 space-y-4 ${className}`}>
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-4 w-16" />
      </div>
      <Skeleton className="h-8 w-2/3" />
      <div className="grid grid-cols-2 gap-4 pt-2">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    </div>
  );
};

export const SkeletonTable: React.FC<{ rows?: number; className?: string }> = ({
  rows = 4,
  className = '',
}) => {
  return (
    <div className={`divide-y divide-neutral-200 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} />
      ))}
    </div>
  );
};

export default Skeleton;
