import './LoadingSkeleton.css';

interface LoadingSkeletonProps {
  count?: number;
}

export default function LoadingSkeleton({ count = 3 }: LoadingSkeletonProps) {
  return (
    <div className="collections-grid">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="skeleton-card">
          <div className="skeleton-header">
            <div className="skeleton-icon"></div>
            <div className="skeleton-title-section">
              <div className="skeleton-title"></div>
              <div className="skeleton-badge"></div>
            </div>
          </div>
          <div className="skeleton-description">
            <div className="skeleton-line"></div>
            <div className="skeleton-line"></div>
            <div className="skeleton-line short"></div>
          </div>
          <div className="skeleton-footer">
            <div className="skeleton-meta">
              <div className="skeleton-status"></div>
              <div className="skeleton-date"></div>
            </div>
            <div className="skeleton-actions">
              <div className="skeleton-button"></div>
              <div className="skeleton-button"></div>
              <div className="skeleton-button"></div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
