import { useMemo, useState } from 'react';
import type { AGUIStreamEvent } from '../types';

interface AgUiEventItem extends AGUIStreamEvent {
  id: string;
  createdAt: number;
  // 允许透传其它字段
  [key: string]: any;
}

interface AgUiEventStreamPanelProps {
  events: AgUiEventItem[];
  tools?: unknown[];
}

const typeLabelMap: Record<string, string> = {
  RUN_STARTED: 'Run Started',
  RUN_FINISHED: 'Run Finished',
  RUN_ERROR: 'Run Error',
  TEXT_MESSAGE_START: 'Text Start',
  TEXT_MESSAGE_CONTENT: 'Text Delta',
  TEXT_MESSAGE_END: 'Text End',
  TOOL_CALL_START: 'Tool Start',
  TOOL_CALL_END: 'Tool End',
  TOOL_CALL_RESULT: 'Tool Result',
  ACTIVITY_SNAPSHOT: 'Activity',
  REASONING_MESSAGE_CHUNK: 'Thinking',
};

function formatTime(ts: number) {
  const d = new Date(ts);
  return d.toLocaleTimeString('en-US', { hour12: false });
}

export function AgUiEventStreamPanel({ events }: AgUiEventStreamPanelProps) {
  const [viewMode, setViewMode] = useState<'aggregated' | 'raw'>('aggregated');

  const sortedEvents = useMemo(
    () => [...events].sort((a, b) => a.createdAt - b.createdAt),
    [events]
  );

  const groupedByType = useMemo(() => {
    const map = new Map<
      string,
      { type: string; label: string; count: number; events: AgUiEventItem[] }
    >();
    for (const e of sortedEvents) {
      const type = e.type || 'UNKNOWN';
      const label = typeLabelMap[type] || type;
      const key = type;
      const existing = map.get(key);
      if (existing) {
        existing.count += 1;
        existing.events.push(e);
      } else {
        map.set(key, { type, label, count: 1, events: [e] });
      }
    }
    return Array.from(map.values());
  }, [sortedEvents]);

  return (
    <div className="agui-sidebar">
      <div className="agui-sidebar-section">
        <div className="agui-sidebar-header">
          <span className="agui-sidebar-title">AG-UI Event Stream</span>
          <span className="agui-sidebar-count">{sortedEvents.length}</span>
        </div>
        <div className="agui-tabs">
          <button
            type="button"
            className={`agui-tab ${viewMode === 'aggregated' ? 'agui-tab-active' : ''}`}
            onClick={() => setViewMode('aggregated')}
          >
            Aggregated
          </button>
          <button
            type="button"
            className={`agui-tab ${viewMode === 'raw' ? 'agui-tab-active' : ''}`}
            onClick={() => setViewMode('raw')}
          >
            Raw
          </button>
        </div>
        {viewMode === 'aggregated' ? (
          <div className="agui-event-list">
            {groupedByType.length === 0 ? (
              <div className="agui-event-empty">AG-UI events will appear here after you send a message.</div>
            ) : (
              groupedByType.map((group) => {
                const first = group.events[0];
                const shortContent =
                  first.delta ||
                  first.message ||
                  (typeof first.content === 'string' ? first.content : '') ||
                  '';
                const preview =
                  shortContent.length > 60 ? `${shortContent.slice(0, 60)}…` : shortContent;
                const ts = first.createdAt;

                return (
                  <div key={group.type} className="agui-event-item">
                    <div className="agui-event-meta">
                      <span
                        className={`agui-event-pill agui-event-pill-${group.type.toLowerCase()}`}
                      >
                        {group.label}
                      </span>
                      <span className="agui-event-count">×{group.count}</span>
                      <span className="agui-event-time">{formatTime(ts)}</span>
                    </div>
                    {preview && <div className="agui-event-preview">{preview}</div>}
                  </div>
                );
              })
            )}
          </div>
        ) : (
          <div className="agui-event-list">
            {sortedEvents.length === 0 ? (
              <div className="agui-event-empty">AG-UI events will appear here after you send a message.</div>
            ) : (
              sortedEvents.map((e) => {
                const type = e.type || 'UNKNOWN';
                const label = typeLabelMap[type] || type;
                const ts = e.createdAt;
                const shortContent =
                  e.delta || e.message || (typeof e.content === 'string' ? e.content : '') || '';
                const preview =
                  shortContent.length > 60 ? `${shortContent.slice(0, 60)}…` : shortContent;

                return (
                  <div key={e.id} className="agui-event-item">
                    <div className="agui-event-meta">
                      <span className={`agui-event-pill agui-event-pill-${type.toLowerCase()}`}>
                        {label}
                      </span>
                      <span className="agui-event-time">{formatTime(ts)}</span>
                    </div>
                    {preview && <div className="agui-event-preview">{preview}</div>}
                    <details className="agui-event-details">
                      <summary>Raw payload</summary>
                      <pre className="agui-event-json">
                        {JSON.stringify(
                          {
                            ...e,
                            id: undefined,
                            createdAt: undefined,
                          },
                          null,
                          2
                        )}
                      </pre>
                    </details>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    </div>
  );
}

