import { Bell, HelpCircle, Plus, ChevronLeft, ChevronRight, X } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useMemo, useRef, useState } from 'react';
import { workflowsApi } from '../api/client';
import type { WorkflowRecord } from '../types';
import './Header.css';

export default function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<WorkflowRecord[]>([]);
  const [loadingWorkflows, setLoadingWorkflows] = useState(false);
  const [workflowsError, setWorkflowsError] = useState<string | null>(null);
  const [openWorkflowIds, setOpenWorkflowIds] = useState<string[]>([]);
  const tabsRef = useRef<HTMLDivElement | null>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const openIdsLoadedRef = useRef(false);
  const OPEN_TABS_STORAGE_KEY = 'workflow_open_tabs';

  const isWorkflowsPage = location.pathname.startsWith('/workflows');
  const workflowId = useMemo(() => {
    const match = location.pathname.match(/^\/workflows\/([^/]+)$/);
    return match ? decodeURIComponent(match[1]) : '';
  }, [location.pathname]);

  useEffect(() => {
    if (!isWorkflowsPage) return;
    let cancelled = false;
    const loadWorkflows = async () => {
      try {
        setLoadingWorkflows(true);
        setWorkflowsError(null);
        const data = await workflowsApi.list();
        if (!cancelled) {
          setWorkflows(data.items || []);
        }
      } catch (error) {
        console.error('Failed to load workflows:', error);
        if (!cancelled) {
          setWorkflows([]);
          setWorkflowsError('加载失败');
        }
      } finally {
        if (!cancelled) {
          setLoadingWorkflows(false);
        }
      }
    };
    loadWorkflows();
    return () => {
      cancelled = true;
    };
  }, [isWorkflowsPage]);

  useEffect(() => {
    if (openIdsLoadedRef.current) return;
    const raw = localStorage.getItem(OPEN_TABS_STORAGE_KEY);
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          setOpenWorkflowIds(parsed.filter((id) => typeof id === 'string'));
        }
      } catch {
        // ignore invalid cache
      }
    }
    openIdsLoadedRef.current = true;
  }, []);

  useEffect(() => {
    if (!openIdsLoadedRef.current) return;
    localStorage.setItem(OPEN_TABS_STORAGE_KEY, JSON.stringify(openWorkflowIds));
  }, [openWorkflowIds]);

  useEffect(() => {
    if (!isWorkflowsPage) return;
    if (!workflowId) return;
    setOpenWorkflowIds((prev) => (prev.includes(workflowId) ? prev : [...prev, workflowId]));
  }, [isWorkflowsPage, workflowId]);

  useEffect(() => {
    if (!isWorkflowsPage) return;
    const updateScrollState = () => {
      const el = tabsRef.current;
      if (!el) return;
      const { scrollLeft, scrollWidth, clientWidth } = el;
      const maxScrollLeft = scrollWidth - clientWidth;
      setCanScrollLeft(scrollLeft > 0);
      setCanScrollRight(scrollLeft < maxScrollLeft - 1);
    };
    updateScrollState();
    const handleResize = () => updateScrollState();
    window.addEventListener('resize', handleResize);
    const el = tabsRef.current;
    if (el) {
      el.addEventListener('scroll', updateScrollState, { passive: true });
    }
    const raf = requestAnimationFrame(updateScrollState);
    return () => {
      window.removeEventListener('resize', handleResize);
      if (el) {
        el.removeEventListener('scroll', updateScrollState);
      }
      cancelAnimationFrame(raf);
    };
  }, [isWorkflowsPage, workflows.length, loadingWorkflows, workflowsError]);

  const workflowMap = useMemo(() => {
    return new Map(workflows.map((wf) => [wf.id, wf]));
  }, [workflows]);

  const openWorkflows = useMemo(() => {
    return openWorkflowIds
      .map((id) => workflowMap.get(id))
      .filter(Boolean) as WorkflowRecord[];
  }, [openWorkflowIds, workflowMap]);
  
  return (
    <header className="header">
      <div className="header-main">
        <div className="header-left">
          <div className="logo">
            <div className="logo-icon">
              <svg
                width="50"
                height="50"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                {/* 外层神经网络/能量环 */}
                <circle
                  cx="12"
                  cy="12"
                  r="8"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {/* 节点 */}
                <circle cx="7.5" cy="10" r="1.3" fill="currentColor" />
                <circle cx="16.5" cy="10" r="1.3" fill="currentColor" />
                <circle cx="12" cy="16" r="1.3" fill="currentColor" />
                {/* 连接边，象征智能体路由/决策 */}
                <path
                  d="M7.5 10L12 16L16.5 10"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {/* 顶部输入火花，象征 AI 感知/指令入口 */}
                <path
                  d="M12 5L12 7.4"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
                <circle cx="12" cy="4.2" r="0.9" fill="currentColor" />
              </svg>
            </div>
            <span className="logo-text">SuperRAG</span>
          </div>
          <nav className="header-nav">
            <Link 
              to="/workflows" 
              className={`header-nav-link ${location.pathname.startsWith('/workflows') ? 'active' : ''}`}
            >
              Editor
            </Link>
            <Link 
              to="/node-manager" 
              className={`header-nav-link ${location.pathname === '/node-manager' ? 'active' : ''}`}
            >
              Node Manager
            </Link>
          </nav>
        </div>
        <div className="header-right">
          <button className="icon-button">
            <Bell size={20} />
            <span className="badge">3</span>
          </button>
          <button className="icon-button">
            <HelpCircle size={20} />
          </button>
        </div>
      </div>
      {isWorkflowsPage && (
        <div className="header-subbar">
          <button
            type="button"
            className={`workflow-scroll-btn ${canScrollLeft ? '' : 'is-hidden'}`}
            onClick={() => tabsRef.current?.scrollBy({ left: -200, behavior: 'smooth' })}
            aria-label="Scroll left"
            disabled={!canScrollLeft}
          >
            <ChevronLeft size={16} />
          </button>
          <div className="workflow-tabs" ref={tabsRef}>
            {loadingWorkflows ? (
              <div className="workflow-tab is-loading">加载中...</div>
            ) : workflowsError ? (
              <div className="workflow-tab is-error">{workflowsError}</div>
            ) : (
              <>
                {openWorkflows.map((wf) => {
                  const title = wf.title || wf.name || wf.id;
                  return (
                    <button
                      key={wf.id}
                      type="button"
                      className={`workflow-tab ${wf.id === workflowId ? 'is-active' : ''}`}
                      title={title}
                      onClick={() => navigate(`/workflows/${wf.id}`)}
                    >
                      <span className="workflow-tab-label">{title}</span>
                      <span
                        className="workflow-tab-close"
                        role="button"
                        aria-label="Close tab"
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          setOpenWorkflowIds((prev) => {
                            const remaining = prev.filter((id) => id !== wf.id);
                            if (wf.id === workflowId) {
                              if (remaining.length > 0) {
                                const nextId = remaining[remaining.length - 1];
                                navigate(`/workflows/${nextId}`);
                              } else {
                                navigate('/workflows');
                              }
                            }
                            return remaining;
                          });
                        }}
                      >
                        <X size={12} />
                      </span>
                    </button>
                  );
                })}
                <Link
                  to="/workflows"
                  className="workflow-tab-add"
                  title="New blank editor"
                  aria-label="New blank editor"
                >
                  <Plus size={18} />
                </Link>
              </>
            )}
          </div>
          <button
            type="button"
            className={`workflow-scroll-btn ${canScrollRight ? '' : 'is-hidden'}`}
            onClick={() => tabsRef.current?.scrollBy({ left: 200, behavior: 'smooth' })}
            aria-label="Scroll right"
            disabled={!canScrollRight}
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </header>
  );
}
