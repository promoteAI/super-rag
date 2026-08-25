import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ChevronDown, MoreVertical, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { modelProvidersApi } from '../api/client';
import type { ModelProviderModel, ModelProviderModelsResponse, ModelProviderModelCreate } from '../types';
import './ModelProviderModelsPage.css';

type ApiFilter = 'completion' | 'embedding' | 'rerank';
type ModelFormState = Omit<
  ModelProviderModelCreate,
  'context_window' | 'max_input_tokens' | 'max_output_tokens'
> & {
  context_window: number | null | string;
  max_input_tokens: number | null | string;
  max_output_tokens: number | null | string;
};

const apiFilterOptions: Array<{ value: ApiFilter; label: string }> = [
  { value: 'completion', label: 'Completion' },
  { value: 'embedding', label: 'Embedding' },
  { value: 'rerank', label: 'Rerank' },
];

export default function ModelProviderModelsPage() {
  const { providerName } = useParams();
  const navigate = useNavigate();
  const [models, setModels] = useState<ModelProviderModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [apiFilter, setApiFilter] = useState<ApiFilter>('completion');
  const [apiMenuOpen, setApiMenuOpen] = useState(false);
  const [openActionMenu, setOpenActionMenu] = useState<string | null>(null);
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
  const [agentToggles, setAgentToggles] = useState<Record<string, boolean>>({});
  const [collectionToggles, setCollectionToggles] = useState<Record<string, boolean>>({});
  const [toggleUpdatingKey, setToggleUpdatingKey] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelProviderModel | null>(null);
  const [formData, setFormData] = useState<ModelFormState>({
    model: '',
    api: 'completion',
    custom_llm_provider: '',
    context_window: null,
    max_input_tokens: null,
    max_output_tokens: null,
  });

  const resolvedProviderName = useMemo(
    () => (providerName ? decodeURIComponent(providerName) : ''),
    [providerName]
  );

  const loadModels = useCallback(async () => {
    if (!resolvedProviderName) return;
    try {
      setLoading(true);
      setErrorMessage('');
      const data = await modelProvidersApi.listModels({
        provider_name: resolvedProviderName,
      });
      const list = Array.isArray(data)
        ? data
        : (data as ModelProviderModelsResponse).items ||
          (data as ModelProviderModelsResponse).models ||
          [];
      setModels(list);
    } catch (error) {
      console.error('Failed to load provider models:', error);
      setErrorMessage('Failed to load models. Please refresh and try again.');
    } finally {
      setLoading(false);
    }
  }, [resolvedProviderName]);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  useEffect(() => {
    const nextAgent: Record<string, boolean> = {};
    const nextCollection: Record<string, boolean> = {};
    models.forEach((model) => {
      const key = `${model.provider_name}-${model.api}-${model.model}`;
      const tags = model.tags ?? [];
      nextAgent[key] = tags.includes('enable_for_agent');
      nextCollection[key] = tags.includes('enable_for_collection');
    });
    setAgentToggles(nextAgent);
    setCollectionToggles(nextCollection);
  }, [models]);

  useEffect(() => {
    if (!resolvedProviderName) return;
    setFormData((prev) => ({
      ...prev,
      custom_llm_provider: resolvedProviderName,
    }));
  }, [resolvedProviderName]);

  const filteredModels = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return models.filter((model) => {
      const matchesApi = model.api?.toLowerCase() === apiFilter;
      if (!matchesApi) return false;
      if (!query) return true;
      return (
        model.model?.toLowerCase().includes(query) ||
        model.custom_llm_provider?.toLowerCase().includes(query)
      );
    });
  }, [models, apiFilter, searchQuery]);

  const filteredModelKeys = useMemo(
    () => filteredModels.map((model) => `${model.provider_name}-${model.api}-${model.model}`),
    [filteredModels]
  );

  const allSelected = filteredModelKeys.length > 0 && filteredModelKeys.every((key) => selectedModels.has(key));

  const handleTagToggle = async (model: ModelProviderModel, target: 'agent' | 'collection') => {
    if (!resolvedProviderName) return;
    const key = `${model.provider_name}-${model.api}-${model.model}`;
    const isCurrentlyOn = target === 'agent' ? agentToggles[key] : collectionToggles[key];
    const enableTag = target === 'agent' ? 'enable_for_agent' : 'enable_for_collection';
    const currentTags = model.tags ?? [];
    const nextTags = isCurrentlyOn
      ? currentTags.filter((tag) => tag !== enableTag)
      : Array.from(new Set([...currentTags, enableTag]));

    const payload = {
      model: model.model,
      api: model.api,
      custom_llm_provider: model.custom_llm_provider || resolvedProviderName,
      context_window: model.context_window ?? null,
      max_input_tokens: model.max_input_tokens ?? null,
      max_output_tokens: model.max_output_tokens ?? null,
      tags: nextTags,
    };

    try {
      setToggleUpdatingKey(`${key}-${target}`);
      await modelProvidersApi.updateModel(
        model.provider_name || resolvedProviderName,
        model.api,
        model.model,
        payload
      );
      setModels((prev) =>
        prev.map((m) =>
          m.provider_name === model.provider_name &&
          m.api === model.api &&
          m.model === model.model
            ? { ...m, tags: nextTags }
            : m
        )
      );
      if (target === 'agent') {
        setAgentToggles((prev) => ({ ...prev, [key]: !isCurrentlyOn }));
      } else {
        setCollectionToggles((prev) => ({ ...prev, [key]: !isCurrentlyOn }));
      }
    } catch (error) {
      console.error('Failed to update model tags:', error);
      alert('Failed to update model tags. Please try again.');
    } finally {
      setToggleUpdatingKey(null);
    }
  };

  return (
    <div className="models-page">
      <div className="models-header">
        <div className="models-breadcrumb">
          <button className="breadcrumb-back" onClick={() => navigate(-1)} aria-label="Back">
            <ArrowLeft size={16} />
          </button>
          <span>Model Provider</span>
          <span className="breadcrumb-separator">›</span>
          <span>{resolvedProviderName || '-'}</span>
          <span className="breadcrumb-separator">›</span>
          <span>Models</span>
        </div>
        <h1>Models</h1>
        <p>
          This section allows you to connect and customize your preferred Large Language Model
          (LLM) providers and models for personal use. Set up API keys, choose models, and adjust
          settings to enhance your AI experience.
        </p>
      </div>

      <div className="models-toolbar">
        <div className="filters">
          <div className="api-filter">
            <button
              className="api-filter-button"
              onClick={() => setApiMenuOpen((prev) => !prev)}
              type="button"
            >
              {apiFilterOptions.find((option) => option.value === apiFilter)?.label}
              <ChevronDown size={16} />
            </button>
            {apiMenuOpen && (
              <div className="api-filter-menu">
                {apiFilterOptions.map((option) => (
                  <button
                    key={option.value}
                    className={`api-filter-option ${option.value === apiFilter ? 'active' : ''}`}
                    onClick={() => {
                      setApiFilter(option.value);
                      setApiMenuOpen(false);
                    }}
                    type="button"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="models-search">
            <Search size={16} />
            <input
              type="text"
              placeholder="Search Models"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>
        </div>
        <div className="toolbar-actions">
          <button
            className="btn-primary"
            type="button"
            onClick={() => {
              setEditingModel(null);
              setFormData({
                model: '',
                api: apiFilter,
                custom_llm_provider: resolvedProviderName,
                context_window: null,
                max_input_tokens: null,
                max_output_tokens: null,
              });
              setShowCreateModal(true);
            }}
          >
            <Plus size={16} />
            Add Model
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loading-state">Loading...</div>
      ) : errorMessage ? (
        <div className="error-state">{errorMessage}</div>
      ) : (
        <div className="models-table-container">
          <table className="models-table">
            <thead>
              <tr>
                <th className="checkbox-cell" rowSpan={2}>
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={() => {
                      setSelectedModels(() =>
                        allSelected ? new Set() : new Set(filteredModelKeys)
                      );
                    }}
                  />
                </th>
                <th rowSpan={2}>Model Name</th>
                <th colSpan={3} className="llm-params-header">LLM params</th>
                <th rowSpan={2}>Agent</th>
                <th rowSpan={2}>Collection</th>
                <th rowSpan={2}>API Type</th>
                <th rowSpan={2}></th>
              </tr>
              <tr>
                <th className="llm-sub-header">Context</th>
                <th className="llm-sub-header">Max Input</th>
                <th className="llm-sub-header">Max Output</th>
              </tr>
            </thead>
            <tbody>
              {filteredModels.length === 0 ? (
                <tr>
                  <td colSpan={5} className="empty-row">
                    No results.
                  </td>
                </tr>
              ) : (
                filteredModels.map((model) => {
                  const key = `${model.provider_name}-${model.api}-${model.model}`;
                  return (
                    <tr key={key}>
                      <td className="checkbox-cell">
                        <input
                          type="checkbox"
                          checked={selectedModels.has(key)}
                          onChange={() => {
                            setSelectedModels((prev) => {
                              const next = new Set(prev);
                              if (next.has(key)) {
                                next.delete(key);
                              } else {
                                next.add(key);
                              }
                              return next;
                            });
                          }}
                        />
                      </td>
                      <td className="model-name">
                        <div className="model-name-main">{model.model || '-'}</div>
                        {model.tags && model.tags.length > 0 && (
                          <div className="model-tags">
                            {model.tags.map((tag) => (
                              <span key={tag} className="model-tag">
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="llm-param">{model.context_window ?? '-'}</td>
                      <td className="llm-param">{model.max_input_tokens ?? '-'}</td>
                      <td className="llm-param">{model.max_output_tokens ?? '-'}</td>
                      <td>
                        <label className="toggle-switch">
                          <input
                            type="checkbox"
                            checked={agentToggles[key] ?? false}
                            onChange={() => handleTagToggle(model, 'agent')}
                            disabled={toggleUpdatingKey === `${key}-agent`}
                          />
                          <span className="toggle-slider"></span>
                        </label>
                      </td>
                      <td>
                        <label className="toggle-switch">
                          <input
                            type="checkbox"
                            checked={collectionToggles[key] ?? false}
                            onChange={() => handleTagToggle(model, 'collection')}
                            disabled={toggleUpdatingKey === `${key}-collection`}
                          />
                          <span className="toggle-slider"></span>
                        </label>
                      </td>
                      <td>
                        <span className="api-badge">{model.api || '-'}</span>
                      </td>
                      <td className="actions-cell">
                        <div className="actions-menu">
                          <button
                            className="menu-trigger"
                            type="button"
                            onClick={() =>
                              setOpenActionMenu((prev) => (prev === key ? null : key))
                            }
                            aria-label="Actions"
                          >
                            <MoreVertical size={16} />
                          </button>
                          {openActionMenu === key && (
                            <div className="menu-dropdown">
                              <button
                                className="menu-item"
                                type="button"
                                onClick={() => {
                                  setOpenActionMenu(null);
                                  setEditingModel(model);
                                  setFormData({
                                    model: model.model || '',
                                    api: model.api || 'completion',
                                    custom_llm_provider:
                                      model.custom_llm_provider || resolvedProviderName,
                                    context_window: model.context_window ?? null,
                                    max_input_tokens: model.max_input_tokens ?? null,
                                    max_output_tokens: model.max_output_tokens ?? null,
                                  });
                                  setShowCreateModal(true);
                                }}
                              >
                                <Pencil size={16} />
                                <span>Edit</span>
                              </button>
                              <button
                                className="menu-item delete"
                                type="button"
                                onClick={() => {
                                  setOpenActionMenu(null);
                                  const modelName = model.model || '';
                                  if (!resolvedProviderName || !model.api || !modelName) {
                                    alert('Missing model information.');
                                    return;
                                  }
                                  const confirmed = window.confirm(
                                    `Delete model "${modelName}"? This action cannot be undone.`
                                  );
                                  if (!confirmed) return;
                                  setSubmitting(true);
                                  modelProvidersApi
                                    .deleteModel(resolvedProviderName, model.api, modelName)
                                    .then(() => loadModels())
                                    .catch((error) => {
                                      console.error('Failed to delete model:', error);
                                      alert('Failed to delete model. Please try again.');
                                    })
                                    .finally(() => setSubmitting(false));
                                }}
                              >
                                <Trash2 size={16} />
                                <span>Delete</span>
                              </button>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
          <div className="table-footer">
            <div className="table-info">
              {selectedModels.size} of {filteredModels.length} row(s) selected.
            </div>
            <div className="table-pagination">
              <span>Rows per page</span>
              <select defaultValue="20">
                <option value="20">20</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </select>
              <span>Page 1 of 1</span>
              <div className="pagination-buttons">
                <button disabled>&lt;&lt;</button>
                <button disabled>&lt;</button>
                <button disabled>&gt;</button>
                <button disabled>&gt;&gt;</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h2>{editingModel ? 'Edit Model' : 'Add Model'}</h2>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>
                ×
              </button>
            </div>
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                if (!resolvedProviderName) return;
                if (!formData.model.trim()) {
                  alert('Please enter the model name');
                  return;
                }
                const parseNumber = (value: number | null | string) => {
                  if (value === null) return null;
                  if (typeof value === 'number') return value;
                  const trimmed = value.trim();
                  if (!trimmed) return null;
                  const parsed = Number(trimmed);
                  return Number.isNaN(parsed) ? null : parsed;
                };
                const payload: ModelProviderModelCreate = {
                  model: formData.model.trim(),
                  api: formData.api,
                  custom_llm_provider: formData.custom_llm_provider?.trim() || resolvedProviderName,
                  context_window: parseNumber(formData.context_window as number | string),
                  max_input_tokens: parseNumber(formData.max_input_tokens as number | string),
                  max_output_tokens: parseNumber(formData.max_output_tokens as number | string),
                };
                if (
                  (formData.context_window !== null && payload.context_window === null) ||
                  (formData.max_input_tokens !== null && payload.max_input_tokens === null) ||
                  (formData.max_output_tokens !== null && payload.max_output_tokens === null)
                ) {
                  alert('LLM params must be numbers');
                  return;
                }
                try {
                  setSubmitting(true);
                  if (editingModel) {
                    await modelProvidersApi.updateModel(
                      resolvedProviderName,
                      editingModel.api,
                      editingModel.model,
                      payload
                    );
                  } else {
                    await modelProvidersApi.createModel(resolvedProviderName, payload);
                  }
                  setShowCreateModal(false);
                  loadModels();
                } catch (error) {
                  console.error('Failed to save model:', error);
                  alert(`Failed to ${editingModel ? 'update' : 'create'} model. Please try again.`);
                } finally {
                  setSubmitting(false);
                }
              }}
            >
              <div className="modal-body">
                <div className="form-group">
                  <label>Model Name</label>
                  <input
                    type="text"
                    placeholder="Enter the model name"
                    value={formData.model}
                    onChange={(event) =>
                      setFormData((prev) => ({ ...prev, model: event.target.value }))
                    }
                    disabled={!!editingModel}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>API Type</label>
                  <div className={`api-type-group ${editingModel ? 'is-locked' : ''}`}>
                    {apiFilterOptions.map((option) => (
                      <label
                        key={option.value}
                        className="api-type-option"
                        onClick={(event) => {
                          if (editingModel) {
                            event.preventDefault();
                          }
                        }}
                      >
                        <input
                          type="radio"
                          name="apiType"
                          value={option.value}
                          checked={formData.api === option.value}
                          onChange={() => {
                            if (editingModel) return;
                            setFormData((prev) => ({ ...prev, api: option.value }));
                          }}
                          aria-disabled={!!editingModel}
                        />
                        <span>{option.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div className="form-group">
                  <label>LLM Provider</label>
                  <select
                    value={formData.custom_llm_provider || resolvedProviderName}
                    onChange={(event) =>
                      setFormData((prev) => ({ ...prev, custom_llm_provider: event.target.value }))
                    }
                  >
                    <option value={resolvedProviderName}>{resolvedProviderName || '-'}</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>LLM params</label>
                  <div className="params-grid">
                    <div className="params-field">
                      <span>Context Window</span>
                      <input
                        type="number"
                        value={formData.context_window ?? ''}
                        onChange={(event) =>
                          setFormData((prev) => ({
                            ...prev,
                            context_window: event.target.value,
                          }))
                        }
                      />
                    </div>
                    <div className="params-field">
                      <span>Max Input Tokens</span>
                      <input
                        type="number"
                        value={formData.max_input_tokens ?? ''}
                        onChange={(event) =>
                          setFormData((prev) => ({
                            ...prev,
                            max_input_tokens: event.target.value,
                          }))
                        }
                      />
                    </div>
                    <div className="params-field">
                      <span>Max Output Tokens</span>
                      <input
                        type="number"
                        value={formData.max_output_tokens ?? ''}
                        onChange={(event) =>
                          setFormData((prev) => ({
                            ...prev,
                            max_output_tokens: event.target.value,
                          }))
                        }
                      />
                    </div>
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={submitting}>
                  {submitting ? 'Saving...' : editingModel ? 'Update' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
