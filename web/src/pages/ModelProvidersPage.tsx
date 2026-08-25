import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { modelProvidersApi } from '../api/client';
import type { ModelProvider, ModelProviderCreate, ModelProviderModel } from '../types';
import { Plus, Edit, Trash2, Search, MoreVertical, List, Key } from 'lucide-react';
import { showToast } from '../utils/toast';
import ConfirmDialog from '../components/ConfirmDialog';
import './ModelProvidersPage.css';

export default function ModelProvidersPage() {
  const navigate = useNavigate();
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [models, setModels] = useState<ModelProviderModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ModelProvider | null>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [openMenuProvider, setOpenMenuProvider] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ModelProvider | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [apiKeyTarget, setApiKeyTarget] = useState<ModelProvider | null>(null);
  const [apiKeyValue, setApiKeyValue] = useState('');
  const [isSavingApiKey, setIsSavingApiKey] = useState(false);
  const [disableTarget, setDisableTarget] = useState<ModelProvider | null>(null);
  const [isDisabling, setIsDisabling] = useState(false);

  const loadProviders = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage('');
      const data = await modelProvidersApi.list();
      setProviders(data.providers || []);
      setModels(data.models || []);
    } catch (error) {
      console.error('Failed to load model providers:', error);
      setErrorMessage('Failed to load model providers. Please refresh and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  const isProviderEnabled = useCallback(
    (provider: ModelProvider) =>
      provider.status === 'enable' ||
      (provider.status == null && (Boolean(provider.enabled) || Boolean(provider.api_key))),
    [],
  );

  const handleToggleEnabled = useCallback(
    (provider: ModelProvider) => {
      if (!provider.name) return;
      const enabled = provider.status === 'enable' ||
        (provider.status == null && (Boolean(provider.enabled) || Boolean(provider.api_key)));
      if (enabled) {
        setDisableTarget(provider);
      } else {
        setApiKeyTarget(provider);
        setApiKeyValue(provider.api_key || '');
      }
    },
    [],
  );

  const handleDisableConfirm = useCallback(async () => {
    if (!disableTarget?.name) return;
    try {
      setIsDisabling(true);
      await modelProvidersApi.update(disableTarget.name, { status: 'disable' });
      setDisableTarget(null);
      await loadProviders();
      showToast('Provider disabled.', 'success');
    } catch (error) {
      console.error('Failed to disable provider:', error);
      showToast('Failed to update provider status.', 'error');
    } finally {
      setIsDisabling(false);
    }
  }, [disableTarget, loadProviders]);

  const handleSaveApiKey = async () => {
    if (!apiKeyTarget?.name || !apiKeyValue.trim()) return;
    try {
      setIsSavingApiKey(true);
      await modelProvidersApi.update(apiKeyTarget.name, {
        api_key: apiKeyValue.trim(),
        status: 'enable',
      });
      setApiKeyTarget(null);
      setApiKeyValue('');
      await loadProviders();
      showToast('API Key saved and provider enabled.', 'success');
    } catch (error) {
      console.error('Failed to save API key:', error);
      showToast('Failed to save API key. Please try again.', 'error');
    } finally {
      setIsSavingApiKey(false);
    }
  };

  const handleDeleteClick = useCallback((provider: ModelProvider) => {
    setOpenMenuProvider(null);
    setDeleteTarget(provider);
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget?.name) return;
    try {
      setIsDeleting(true);
      await modelProvidersApi.delete(deleteTarget.name);
      setDeleteTarget(null);
      await loadProviders();
    } catch (error) {
      console.error('Failed to delete provider:', error);
      showToast('Failed to delete provider.', 'error');
    } finally {
      setIsDeleting(false);
    }
  }, [deleteTarget, loadProviders]);

  const handleEdit = useCallback((provider: ModelProvider) => {
    setEditingProvider(provider);
    setShowCreateModal(true);
    setOpenMenuProvider(null);
  }, []);

  const handleViewModels = useCallback((provider: ModelProvider) => {
    if (!provider.name) return;
    setOpenMenuProvider(null);
    navigate(`/model-providers/${encodeURIComponent(provider.name)}/models`);
  }, [navigate]);

  const filteredProviders = providers.filter((provider) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      provider.name?.toLowerCase().includes(query) ||
      provider.label?.toLowerCase().includes(query) ||
      provider.base_url?.toLowerCase().includes(query)
    );
  });

  const modelCountByProvider = models.reduce<Record<string, number>>((acc, model) => {
    acc[model.provider_name] = (acc[model.provider_name] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="model-providers-page">
      <div className="page-header">
        <div className="page-header-content">
          <h1 className="page-title">Model Provider</h1>
          <p className="page-description">
            This section allows you to connect and customize your preferred Large Language Model (LLM) providers and models for personal use. Set up API keys, choose models, and adjust settings to enhance your AI experience.
          </p>
        </div>
      </div>

      <div className="page-content">
        <div className="page-controls">
          <div className="search-box">
            <Search size={18} />
            <input
              type="text"
              placeholder="Search model provider"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <button
            className="btn-primary"
            onClick={() => {
              setEditingProvider(null);
              setShowCreateModal(true);
            }}
          >
            <Plus size={18} />
            Add Provider
          </button>
        </div>

        {loading ? (
          <div className="loading-state">Loading...</div>
        ) : errorMessage ? (
          <div className="error-state">{errorMessage}</div>
        ) : (
          <div className="providers-table-container">
            <table className="providers-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Base Url</th>
                  <th>Models</th>
                  <th>Scope</th>
                  <th>Enabled</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredProviders.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="empty-row">
                      {searchQuery ? 'No providers found matching your search.' : 'No model providers yet. Add your first provider!'}
                    </td>
                  </tr>
                ) : (
                  filteredProviders.map((provider) => (
                    <tr key={provider.name}>
                      <td className="provider-name">{provider.label || provider.name || '-'}</td>
                      <td className="provider-url">{provider.base_url || '-'}</td>
                      <td className="provider-models">{modelCountByProvider[provider.name] || 0}</td>
                      <td>
                        <span className={`scope-badge ${provider.user_id === 'public' ? 'public' : 'private'}`}>
                          {provider.user_id === 'public' ? 'Public' : 'Private'}
                        </span>
                      </td>
                      <td>
                        <label className="toggle-switch">
                          <input
                            type="checkbox"
                            checked={isProviderEnabled(provider)}
                            onChange={() => handleToggleEnabled(provider)}
                          />
                          <span className="toggle-slider"></span>
                        </label>
                      </td>
                      <td className="actions-cell">
                        <div className="actions-menu">
                          <button
                            className="menu-trigger"
                            onClick={() => setOpenMenuProvider((prev) => (prev === provider.name ? null : provider.name))}
                            title="Actions"
                          >
                            <MoreVertical size={16} />
                          </button>
                          {openMenuProvider === provider.name && (
                            <div className="menu-dropdown">
                              <button className="menu-item" onClick={() => handleViewModels(provider)}>
                                <List size={16} />
                                <span>Models</span>
                              </button>
                              <button className="menu-item" onClick={() => handleEdit(provider)}>
                                <Edit size={16} />
                                <span>Edit</span>
                              </button>
                              <button className="menu-item" onClick={() => { setOpenMenuProvider(null); setApiKeyTarget(provider); setApiKeyValue(provider.api_key || ''); }}>
                                <Key size={16} />
                                <span>API Key</span>
                              </button>
                              <button className="menu-item delete" onClick={() => handleDeleteClick(provider)}>
                                <Trash2 size={16} />
                                <span>Delete</span>
                              </button>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            {filteredProviders.length > 0 && (
              <div className="table-footer">
                <div className="table-info">
                  0 of {filteredProviders.length} row(s) selected.
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
            )}
          </div>
        )}
      </div>

      {showCreateModal && (
        <CreateProviderModal
          provider={editingProvider}
          onClose={() => {
            setShowCreateModal(false);
            setEditingProvider(null);
          }}
          onSuccess={() => {
            setShowCreateModal(false);
            setEditingProvider(null);
            loadProviders();
          }}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="Are you absolutely sure?"
        description={`This action cannot be undone. This will permanently delete provider "${deleteTarget?.label || deleteTarget?.name || ''}" and all its associated models.`}
        confirmText="Continue"
        loading={isDeleting}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleDeleteConfirm}
      />

      <ConfirmDialog
        open={!!disableTarget}
        title="Are you absolutely sure?"
        description="Confirm disabling this Provider"
        confirmText="Continue"
        loading={isDisabling}
        loadingText="Disabling..."
        onCancel={() => setDisableTarget(null)}
        onConfirm={handleDisableConfirm}
      />

      {apiKeyTarget && (
        <div className="modal-overlay" onClick={() => { if (!isSavingApiKey) { setApiKeyTarget(null); setApiKeyValue(''); } }}>
          <div className="modal-content api-key-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>API Key</h2>
              <button
                className="modal-close"
                onClick={() => { setApiKeyTarget(null); setApiKeyValue(''); }}
                disabled={isSavingApiKey}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <textarea
                  className="api-key-input"
                  value={apiKeyValue}
                  onChange={(e) => setApiKeyValue(e.target.value)}
                  placeholder="Please enter the api key for the model provider."
                  rows={3}
                  disabled={isSavingApiKey}
                />
              </div>
              <p className="api-key-description">
                To access the AI model's capabilities, you need to provide a valid API Key from your chosen model provider. This key serves as a secure authentication method, allowing the system to process your requests while maintaining privacy and usage control.
              </p>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => { setApiKeyTarget(null); setApiKeyValue(''); }}
                disabled={isSavingApiKey}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={handleSaveApiKey}
                disabled={isSavingApiKey || !apiKeyValue.trim()}
              >
                {isSavingApiKey ? 'Saving...' : 'Continue'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface CreateProviderModalProps {
  provider: ModelProvider | null;
  onClose: () => void;
  onSuccess: () => void;
}

function CreateProviderModal({ provider, onClose, onSuccess }: CreateProviderModalProps) {
  const [formData, setFormData] = useState<ModelProviderCreate>({
    name: provider?.name || '',
    label: provider?.label || '',
    base_url: provider?.base_url || '',
    completion_dialect: provider?.completion_dialect || 'openai',
    embedding_dialect: provider?.embedding_dialect || 'openai',
    rerank_dialect: provider?.rerank_dialect || 'jina_ai',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.label?.trim()) {
      showToast('Please enter a provider name.', 'error');
      return;
    }

    try {
      setSubmitting(true);
      const payload: ModelProviderCreate = {
        ...formData,
        name: formData.name?.trim() || formData.label?.trim() || '',
        label: formData.label?.trim() || formData.name?.trim() || '',
      };
      if (provider?.name) {
        // Update existing provider
        await modelProvidersApi.update(provider.name, {
          name: payload.name,
          label: payload.label,
          base_url: payload.base_url,
          completion_dialect: payload.completion_dialect,
          embedding_dialect: payload.embedding_dialect,
          rerank_dialect: payload.rerank_dialect,
        });
      } else {
        // Create new provider
        await modelProvidersApi.create(payload);
      }
      onSuccess();
    } catch (error) {
      console.error('Failed to save provider:', error);
      showToast('Failed to save provider. Please try again.', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{provider ? 'Edit Provider' : 'Add Provider'}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label>Name</label>
              <input
                type="text"
                value={formData.label}
                onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                placeholder="Provider display name."
                required
              />
            </div>
            <div className="form-group">
              <label>Base URL</label>
              <input
                type="url"
                value={formData.base_url}
                onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                placeholder="Api base url"
              />
              <div className="form-helper">
                The LLM API baseUrl refers to the root endpoint URL used to access a Large Language Model (LLM) API service.
              </div>
            </div>
            <div className="form-group">
              <label>API Dialect</label>
              <div className="dialect-grid">
                <div className="dialect-field">
                  <span>Completion</span>
                  <input
                    type="text"
                    value={formData.completion_dialect}
                    onChange={(e) => setFormData({ ...formData, completion_dialect: e.target.value })}
                  />
                </div>
                <div className="dialect-field">
                  <span>Embedding</span>
                  <input
                    type="text"
                    value={formData.embedding_dialect}
                    onChange={(e) => setFormData({ ...formData, embedding_dialect: e.target.value })}
                  />
                </div>
                <div className="dialect-field">
                  <span>Rerank</span>
                  <input
                    type="text"
                    value={formData.rerank_dialect}
                    onChange={(e) => setFormData({ ...formData, rerank_dialect: e.target.value })}
                  />
                </div>
              </div>
              <div className="form-helper">
                Completion API Dialect suggests possible outputs, Embedding API Dialect converts them to vectors, and Rerank API Dialect optimizes their order based on semantic relevance.
              </div>
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
