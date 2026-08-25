import { useEffect, useRef, useState, useId } from 'react';
import { createPortal } from 'react-dom';
import mermaid from 'mermaid';
import './MermaidDiagram.css';

let mermaidInitialized = false;

function initMermaid() {
  if (mermaidInitialized) return;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: 'neutral',
  });
  mermaidInitialized = true;
}

interface MermaidDiagramProps {
  code: string;
  className?: string;
}

export function MermaidDiagram({ code, className }: MermaidDiagramProps) {
  const id = useId().replace(/:/g, '-');
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [zoom, setZoom] = useState(1);

  const MIN_ZOOM = 0.25;
  const MAX_ZOOM = 12;
  const ZOOM_STEP = 0.2;

  useEffect(() => {
    initMermaid();
    const trimmed = String(code).trim();
    if (!trimmed) {
      setSvg(null);
      setError(null);
      return;
    }
    const uniqueId = `mermaid-${id}-${Math.random().toString(36).slice(2, 9)}`;
    setError(null);
    mermaid
      .render(uniqueId, trimmed)
      .then(({ svg: result }) => {
        setSvg(result);
      })
      .catch((err) => {
        setSvg(null);
        setError(err?.message ?? String(err));
      });
  }, [code, id]);

  useEffect(() => {
    if (!fullscreen) return;
    setZoom(1);
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setFullscreen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [fullscreen]);

  const fullscreenContentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!fullscreen || !fullscreenContentRef.current) return;
    const el = fullscreenContentRef.current;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      if (e.deltaY > 0) {
        setZoom((z) => Math.max(MIN_ZOOM, z - ZOOM_STEP));
      } else {
        setZoom((z) => Math.min(MAX_ZOOM, z + ZOOM_STEP));
      }
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [fullscreen]);

  if (error) {
    return (
      <pre className={className} style={{ whiteSpace: 'pre-wrap', fontSize: '0.875rem', color: 'var(--text-tertiary)' }}>
        Mermaid 渲染失败: {error}
      </pre>
    );
  }
  if (svg) {
    const diagram = (
      <div
        className={className}
        style={{ display: 'flex', justifyContent: 'center', margin: '0.75em 0' }}
        role="button"
        tabIndex={0}
        title="View fullscreen"
        onClick={() => setFullscreen(true)}
        onKeyDown={(e) => e.key === 'Enter' && setFullscreen(true)}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    );

    const fullscreenOverlay = fullscreen && (
      <div
        className="mermaid-fullscreen-overlay"
        role="dialog"
        aria-modal="true"
        aria-label="Mermaid diagram fullscreen"
        onClick={() => setFullscreen(false)}
      >
        <div
          ref={fullscreenContentRef}
          className="mermaid-fullscreen-content"
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
          style={{ cursor: zoom > 1 ? 'move' : 'default' }}
          title="Scroll to zoom"
        >
          <div
            className="mermaid-fullscreen-diagram"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'center center',
            }}
            dangerouslySetInnerHTML={{ __html: svg }}
          />
          <button
            type="button"
            className="mermaid-fullscreen-close"
            onClick={() => setFullscreen(false)}
            aria-label="Close fullscreen"
          >
            ×
          </button>
        </div>
      </div>
    );

    return (
      <>
        <div className="mermaid-diagram-wrapper" style={{ cursor: 'pointer' }}>
          {diagram}
        </div>
        {typeof document !== 'undefined' && createPortal(fullscreenOverlay, document.body)}
      </>
    );
  }
  return (
    <div className={className} style={{ padding: '0.75em', color: 'var(--text-tertiary)', fontSize: '0.875rem' }}>
      渲染中...
    </div>
  );
}
