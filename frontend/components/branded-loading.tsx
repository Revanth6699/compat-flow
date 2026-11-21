"use client";

type BrandedLoadingProps = { label: string; detail?: string };

export function BrandedLoading({ label, detail }: BrandedLoadingProps) {
  return (
    <div className="branded-loading" role="status" aria-live="polite" aria-busy="true">
      <span className="branded-loading-orbit" aria-hidden="true"><span className="branded-loading-core">C</span><i /></span>
      <span className="branded-loading-copy">
        <strong>{label}</strong>
        {detail && <small>{detail}</small>}
      </span>
      <span className="branded-loading-pulse" aria-hidden="true"><i /><i /><i /></span>
    </div>
  );
}

export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="loading-skeleton-stack" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => <span className="loading-skeleton-line" key={index} />)}
    </div>
  );
}

export function LoadingMetricCards() {
  return (
    <div className="loading-metric-grid" aria-hidden="true">
      {Array.from({ length: 6 }, (_, index) => (
        <div className="loading-metric-card" key={index}>
          <span className="loading-skeleton-line short" />
          <span className="loading-skeleton-line value" />
          <span className="loading-skeleton-line medium" />
        </div>
      ))}
    </div>
  );
}
