/**
 * 错误边界，与 nodetool web ErrorBoundary 对齐：捕获子组件树错误并展示 fallback，避免整页白屏。
 * 用于包裹工作流编辑等复杂区域。
 */

import React, { type ErrorInfo, type ReactNode } from 'react';

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
};

type State = {
  hasError: boolean;
  error: Error | null;
};

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.props.onError?.(error, errorInfo);
  }

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="error-boundary-fallback" style={{
          padding: '2rem',
          textAlign: 'center',
          maxWidth: '560px',
          margin: '2rem auto',
          border: '1px solid var(--border, #e5e7eb)',
          borderRadius: '8px',
          background: 'var(--surface, #f9fafb)',
        }}>
          <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>出错了</p>
          <p style={{ color: 'var(--muted, #6b7280)', fontSize: '0.875rem', marginBottom: '1rem' }}>
            {this.state.error.message}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              padding: '0.5rem 1rem',
              cursor: 'pointer',
              border: '1px solid var(--border, #e5e7eb)',
              borderRadius: '6px',
              background: '#fff',
            }}
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
