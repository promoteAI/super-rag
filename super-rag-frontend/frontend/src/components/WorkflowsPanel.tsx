import { useEffect, useMemo, useState } from 'react';
import { Search, X, Tag, CheckSquare, Star, LayoutGrid, List, Plus, ChevronUp, Trash2 } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { workflowsApi } from '../api/client';
import type { WorkflowRecord } from '../types';
import './WorkflowsPanel.css';

type WorkflowChip = { label: string; color: string };

const getStatusChip = (status?: string): WorkflowChip | null => {
  if (!status) return null;
  switch (status) {
    case 'PUBLISHED':
      return { label: 'published', color: 'blue' };
    case 'DRAFT':
      return { label: 'draft', color: 'orange' };
    case 'ARCHIVED':
      return { label: 'archived', color: 'grey' };
    case 'ACTIVE':
      return { label: 'active', color: 'green' };
    case 'INACTIVE':
      return { label: 'inactive', color: 'grey' };
    case 'DELETED':
      return { label: 'deleted', color: 'brown' };
    default:
      return null;
  }
};

export default function WorkflowsPanel() {
  const navigate = useNavigate();
  const { id: currentWorkflowId } = useParams<{ id?: string }>();
  const [searchQuery, setSearchQuery] = useState('');
  const [todayCollapsed, setTodayCollapsed] = useState(false);
  const [workflows, setWorkflows] = useState<WorkflowRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    const loadWorkflows = async () => {
      try {
        setLoading(true);
        setLoadError(null);
        const data = await workflowsApi.list();
        setWorkflows(data.items || []);
      } catch (error) {
        console.error('Failed to load workflows:', error);
        setWorkflows([]);
        setLoadError('加载失败，请稍后重试。');
      } finally {
        setLoading(false);
      }
    };
    loadWorkflows();
  }, []);

  const handleDelete = async (e: React.MouseEvent, workflowId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm('确定要删除该工作流吗？')) return;
    try {
      setDeletingId(workflowId);
      await workflowsApi.delete(workflowId);
      setWorkflows((prev) => prev.filter((w) => w.id !== workflowId));
      if (currentWorkflowId === workflowId) {
        navigate('/workflows', { replace: true });
      }
    } catch (err) {
      console.error('Delete workflow failed:', err);
      setLoadError('删除失败，请稍后重试。');
    } finally {
      setDeletingId(null);
    }
  };

  const filtered = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return workflows;
    return workflows.filter((wf) => {
      const title = wf.title?.toLowerCase() || '';
      const name = wf.name?.toLowerCase() || '';
      const description = wf.description?.toLowerCase() || '';
      const id = wf.id?.toLowerCase() || '';
      return (
        title.includes(query) ||
        name.includes(query) ||
        description.includes(query) ||
        id.includes(query)
      );
    });
  }, [searchQuery, workflows]);

  return (
    <aside className="workflows-panel">
      <h2 className="workflows-panel-title">WORKFLOWS</h2>

      <div className="workflows-panel-search-row">
        <div className="workflows-panel-search">
          <Search size={16} className="workflows-panel-search-icon" />
          <input
            type="text"
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="workflows-panel-search-input"
          />
          {searchQuery && (
            <button
              type="button"
              className="workflows-panel-search-clear"
              onClick={() => setSearchQuery('')}
              aria-label="Clear search"
            >
              <X size={14} />
            </button>
          )}
        </div>
        <button type="button" className="workflows-panel-tag-btn" aria-label="Filter by tag">
          <Tag size={18} />
        </button>
      </div>

      <div className="workflows-panel-filters">
        <button type="button" className="workflows-panel-filter-btn" aria-label="Checkbox filter">
          <CheckSquare size={18} />
        </button>
        <button type="button" className="workflows-panel-filter-btn" aria-label="Starred">
          <Star size={18} />
        </button>
        <button type="button" className="workflows-panel-filter-btn active" aria-label="Grid view">
          <LayoutGrid size={18} />
        </button>
        <button type="button" className="workflows-panel-filter-btn" aria-label="List view">
          <List size={18} />
        </button>
        <Link to="/workflows" className="workflows-panel-add-btn" aria-label="Add workflow">
          <Plus size={20} />
        </Link>
      </div>

      <div className="workflows-panel-section">
        <button
          type="button"
          className="workflows-panel-section-header"
          onClick={() => setTodayCollapsed(!todayCollapsed)}
        >
          <span className="workflows-panel-section-title">TODAY</span>
          <ChevronUp
            size={16}
            className={`workflows-panel-section-chevron ${todayCollapsed ? 'collapsed' : ''}`}
          />
        </button>
        {!todayCollapsed && (
          <div className="workflows-panel-cards">
            {loading ? (
              <p className="workflows-panel-empty">加载工作流中...</p>
            ) : loadError ? (
              <p className="workflows-panel-empty">{loadError}</p>
            ) : filtered.length === 0 ? (
              <p className="workflows-panel-empty">No workflows match your search.</p>
            ) : (
              filtered.map((wf) => {
                const statusChip = getStatusChip(wf.status);
                const chips = [statusChip].filter(Boolean) as WorkflowChip[];
                const title = wf.title || wf.name || wf.id || 'Untitled workflow';

                const cardContent = (
                  <>
                    <div className="workflows-panel-card-preview">
                      {chips.map((chip, i) => (
                        <span
                          key={`${chip.label}-${i}`}
                          className={`workflows-panel-chip workflows-panel-chip-${chip.color}`}
                        >
                          {chip.label}
                        </span>
                      ))}
                    </div>
                    <div className="workflows-panel-card-title">{title}</div>
                  </>
                );

                return wf.id ? (
                  <div key={wf.id} className="workflows-panel-card-wrap">
                    <Link to={`/workflows/${wf.id}`} className="workflows-panel-card">
                      {cardContent}
                    </Link>
                    <button
                      type="button"
                      className="workflows-panel-card-delete"
                      onClick={(e) => handleDelete(e, wf.id!)}
                      disabled={deletingId === wf.id}
                      aria-label="Delete workflow"
                      title="Delete workflow"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ) : (
                  <div key={title} className="workflows-panel-card">
                    {cardContent}
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
