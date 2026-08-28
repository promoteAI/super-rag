import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { availableModelsApi, defaultModelsApi } from '../api/client';
import { showToast } from '../utils/toast';
import './DefaultModelsPage.css';

interface ModelOption {
  model: string;
  custom_llm_provider?: string | null;
}

interface ProviderOption {
  name: string;
  label: string;
  completion: ModelOption[];
  embedding: ModelOption[];
  rerank: ModelOption[];
  base_url: string;
  allow_custom_base_url: boolean;
}

interface DefaultConfig {
  scenario: string;
  provider_name?: string | null;
  model?: string | null;
  custom_llm_provider?: string | null;
}

const SCENARIOS = [
  {
    key: 'default_for_collection_completion',
    label: 'Collection Completion',
    description: 'Default model for collection-level completion tasks',
    apiType: 'completion' as const,
  },
  {
    key: 'default_for_agent_completion',
    label: 'Agent Completion',
    description: 'Default model for agent conversation completion',
    apiType: 'completion' as const,
  },
  {
    key: 'default_for_background_task',
    label: 'Background Tasks',
    description: 'Default model for background tasks (chat title generation, etc.)',
    apiType: 'completion' as const,
  },
  {
    key: 'default_for_embedding',
    label: 'Embedding',
    description: 'Default model for document embedding',
    apiType: 'embedding' as const,
  },
  {
    key: 'default_for_rerank',
    label: 'Rerank',
    description: 'Default model for result reranking',
    apiType: 'rerank' as const,
  },
];

export default function DefaultModelsPage() {
  const navigate = useNavigate();
  const [providers, setProviders] = useState<ProviderOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formState, setFormState] = useState<Record<string, { provider: string; model: string; customProvider: string }>>({});

  useEffect(() => {
    loadProviders();
    loadConfigs();
  }, []);

  const loadProviders = async () => {
    try {
      const response = await availableModelsApi.getAvailableModels();
      const providerMap = new Map<string, ProviderOption>();
      for (const item of response.items || []) {
        providerMap.set(item.name, {
          name: item.name,
          label: item.label || item.name,
          completion: item.completion || [],
          embedding: item.embedding || [],
          rerank: item.rerank || [],
          base_url: item.base_url || '',
          allow_custom_base_url: item.allow_custom_base_url,
        });
      }
      setProviders(Array.from(providerMap.values()));
    } catch (e) {
      console.error('Failed to load providers:', e);
    }
  };

  const loadConfigs = async () => {
    try {
      const response = await defaultModelsApi.get();
      const items = response?.items || [];
      const initialState: Record<string, any> = {};
      for (const scenario of SCENARIOS) {
        const config = items.find((c: DefaultConfig) => c.scenario === scenario.key);
        initialState[scenario.key] = {
          provider: config?.provider_name || '',
          model: config?.model || '',
          customProvider: config?.custom_llm_provider || '',
        };
      }
      setFormState(initialState);
    } catch (e) {
      console.error('Failed to load configs:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleProviderChange = (scenarioKey: string, providerName: string) => {
    setFormState(prev => ({
      ...prev,
      [scenarioKey]: {
        ...prev[scenarioKey],
        provider: providerName,
        model: '',
        customProvider: '',
      },
    }));
  };

  const handleModelChange = (scenarioKey: string, modelName: string, customProvider: string) => {
    setFormState(prev => ({
      ...prev,
      [scenarioKey]: {
        ...prev[scenarioKey],
        model: modelName,
        customProvider,
      },
    }));
  };

  const getAvailableModels = (scenarioKey: string): ModelOption[] => {
    const state = formState[scenarioKey];
    const provider = providers.find(p => p.name === state?.provider);
    if (!provider) return [];
    
    const scenario = SCENARIOS.find(s => s.key === scenarioKey);
    if (!scenario) return [];
    
    const models = provider[scenario.apiType];
    return models || [];
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const defaults = SCENARIOS.map(scenario => {
        const state = formState[scenario.key] || { provider: '', model: '', customProvider: '' };
        return {
          scenario: scenario.key,
          provider_name: state.provider || null,
          model: state.model || null,
          custom_llm_provider: state.customProvider || null,
        };
      });
      
      await defaultModelsApi.update({ defaults });
      showToast('Default models updated successfully', 'success');
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Failed to update default models', 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="default-models-page">
        <div className="loading-state">Loading...</div>
      </div>
    );
  }

  return (
    <div className="default-models-page">
      <div className="page-header">
        <div className="page-header-content">
          <h1 className="page-title">Default Models</h1>
          <p className="page-description">
            Configure the default models for different scenarios. These models will be used automatically when no specific model is selected.
          </p>
        </div>
      </div>

      <div className="default-models-grid">
        {SCENARIOS.map(scenario => {
          const state = formState[scenario.key] || { provider: '', model: '', customProvider: '' };
          const availableModels = getAvailableModels(scenario.key);
          
          return (
            <div key={scenario.key} className="scenario-card">
              <div className="scenario-header">
                <h3 className="scenario-title">{scenario.label}</h3>
              </div>
              <p className="scenario-desc">{scenario.description}</p>
              
              <div className="form-group">
                <label>Provider</label>
                <select
                  value={state.provider}
                  onChange={e => handleProviderChange(scenario.key, e.target.value)}
                  className="form-select"
                >
                  <option value="">-- Select Provider --</option>
                  {providers.map(p => (
                    <option key={p.name} value={p.name}>{p.label}</option>
                  ))}
                </select>
              </div>
              
              <div className="form-group">
                <label>Model</label>
                <select
                  value={state.model}
                  onChange={e => handleModelChange(scenario.key, e.target.value, state.customProvider)}
                  disabled={!state.provider}
                  className="form-select"
                >
                  <option value="">-- Select Model --</option>
                  {availableModels.map(m => (
                    <option key={m.model} value={m.model}>{m.model}</option>
                  ))}
                </select>
              </div>
              
              {state.provider && providers.find(p => p.name === state.provider)?.allow_custom_base_url && (
                <div className="form-group">
                  <label>Custom Provider (LLM dialect)</label>
                  <input
                    type="text"
                    value={state.customProvider}
                    onChange={e => handleModelChange(scenario.key, state.model, e.target.value)}
                    placeholder="e.g., openai, anthropic, bedrock"
                    className="form-input"
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="form-actions">
        <button className="btn-secondary" onClick={() => navigate(-1)}>
          Cancel
        </button>
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>
    </div>
  );
}