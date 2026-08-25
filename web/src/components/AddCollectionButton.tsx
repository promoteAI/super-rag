import { useState, useEffect, useRef } from 'react';
import { Plus, X } from 'lucide-react';
import { collectionsApi, availableModelsApi } from '../api/client';
import type { CollectionCreate, ModelConfig } from '../types';
import { showToast } from '../utils/toast';
import './AddCollectionButton.css';

interface AddCollectionButtonProps {
  onCollectionCreated?: () => void;
}

interface IndexType {
  id: string;
  name: string;
  description: string;
  required: boolean;
}

const INDEX_TYPES: IndexType[] = [
  {
    id: 'vectorAndFulltext',
    name: 'Vector & Fulltext',
    description: 'Combines vector similarity search with keyword-based retrieval for comprehensive and accurate results.',
    required: true,
  },
  {
    id: 'graph',
    name: 'Graph',
    description: 'Stores data as nodes (entities) and edges (relationships), enabling complex relational.',
    required: false,
  },
  {
    id: 'summary',
    name: 'Summary',
    description: 'Indexes summaries or metadata of long documents instead of raw content for faster.',
    required: false,
  },
  {
    id: 'vision',
    name: 'Vision',
    description: 'Encodes visual content (images/videos) into feature vectors for content-based retrieval.',
    required: false,
  },
];

// 默认模型列表（作为后备）
const DEFAULT_EMBEDDING_MODELS = [
  'text-embedding-v4',
  'text-embedding-3-large',
  'text-embedding-3-small',
  'text-embedding-ada-002',
];

const DEFAULT_COMPLETION_MODELS = [
  'google/gemini-2.5-flash',
  'google/gemini-2.0-flash',
  'gpt-4o',
  'gpt-4o-mini',
  'gpt-4-turbo',
  'claude-3-5-sonnet',
  'claude-3-opus',
];

export default function AddCollectionButton({ onCollectionCreated }: AddCollectionButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [embeddingModels, setEmbeddingModels] = useState<string[]>(DEFAULT_EMBEDDING_MODELS);
  const [completionModels, setCompletionModels] = useState<string[]>(DEFAULT_COMPLETION_MODELS);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [formData, setFormData] = useState<CollectionCreate>({
    title: '',
    description: '',
    config: {
      indexTypes: {
        vectorAndFulltext: true,
        graph: false,
        summary: false,
        vision: false,
      },
      embeddingModel: 'text-embedding-v4',
      completionModel: 'google/gemini-2.5-flash',
    },
  });
  const titleInputRef = useRef<HTMLInputElement>(null);

  // 获取可用模型
  useEffect(() => {
    const loadAvailableModels = async () => {
      try {
        setModelsLoading(true);
        const response = await availableModelsApi.getAvailableModels();
        
        // 从所有模型提供者中提取 embedding 和 completion 模型
        const embeddingModelSet = new Set<string>();
        const completionModelSet = new Set<string>();
        
        response.items?.forEach((item) => {
          // 提取 embedding 模型
          item.embedding?.forEach((model: ModelConfig) => {
            if (model.model) {
              embeddingModelSet.add(model.model);
            }
          });
          
          // 提取 completion 模型
          item.completion?.forEach((model: ModelConfig) => {
            if (model.model) {
              completionModelSet.add(model.model);
            }
          });
        });
        
        // 转换为数组并排序
        const embeddingList = Array.from(embeddingModelSet).sort();
        const completionList = Array.from(completionModelSet).sort();
        
        // 更新模型列表
        if (embeddingList.length > 0) {
          setEmbeddingModels(embeddingList);
          // 如果当前选择的模型不在新列表中，使用第一个模型
          setFormData((prev) => {
            const currentModel = prev.config?.embeddingModel || '';
            if (!embeddingList.includes(currentModel)) {
              return {
                ...prev,
                config: {
                  ...prev.config,
                  embeddingModel: embeddingList[0],
                },
              };
            }
            return prev;
          });
        }
        
        if (completionList.length > 0) {
          setCompletionModels(completionList);
          // 如果当前选择的模型不在新列表中，使用第一个模型
          setFormData((prev) => {
            const currentModel = prev.config?.completionModel || '';
            if (!completionList.includes(currentModel)) {
              return {
                ...prev,
                config: {
                  ...prev.config,
                  completionModel: completionList[0],
                },
              };
            }
            return prev;
          });
        }
      } catch (error) {
        console.error('Failed to load available models:', error);
        // 使用默认模型列表
      } finally {
        setModelsLoading(false);
      }
    };
    
    // 当模态框打开时加载模型
    if (isOpen) {
      loadAvailableModels();
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && titleInputRef.current) {
      titleInputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isCreating) {
        handleClose();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, isCreating]);

  const handleClose = () => {
    if (isCreating) return;
    setIsOpen(false);
    setFormData({
      title: '',
      description: '',
      config: {
        indexTypes: {
          vectorAndFulltext: true,
          graph: false,
          summary: false,
          vision: false,
        },
        embeddingModel: 'text-embedding-v4',
        completionModel: 'google/gemini-2.5-flash',
      },
    });
  };

  const handleIndexTypeToggle = (indexId: string) => {
    const indexType = INDEX_TYPES.find((t) => t.id === indexId);
    if (indexType?.required) return; // 不能关闭必需的索引类型

    setFormData((prev) => {
      const currentConfig = prev.config || {};
      const currentIndexTypes = currentConfig.indexTypes || {};
      return {
        ...prev,
        config: {
          ...currentConfig,
          indexTypes: {
            ...currentIndexTypes,
            [indexId]: !currentIndexTypes[indexId],
          },
        },
      };
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.title?.trim()) {
      return;
    }

    try {
      setIsCreating(true);
      
      // 转换前端格式到后端期望的格式
      const indexTypes = formData.config?.indexTypes || {};
      const embeddingModel = formData.config?.embeddingModel || '';
      const completionModel = formData.config?.completionModel || '';
      
      // 构建后端期望的config格式
      const backendConfig: any = {
        source: 'system',
        enable_vector_and_fulltext: indexTypes.vectorAndFulltext || true,
        enable_knowledge_graph: indexTypes.graph ? true : null,
        enable_summary: indexTypes.summary || false,
        enable_vision: indexTypes.vision ? true : null,
        embedding: {
          model: embeddingModel,
          model_service_provider: 'openai',
          custom_llm_provider: 'openai',
          temperature: null,
          max_tokens: null,
          max_completion_tokens: 9482,
          timeout: null,
          top_n: null,
          tags: [],
        },
        completion: {
          model: completionModel,
          model_service_provider: 'openai',
          custom_llm_provider: 'openai',
          temperature: null,
          max_tokens: null,
          max_completion_tokens: 9482,
          timeout: null,
          top_n: null,
          tags: [],
        },
      };
      
      // 构建后端期望的请求体
      const backendData: CollectionCreate = {
        title: formData.title,
        description: formData.description,
        type: 'document',
        config: backendConfig,
        source: {},
      };
      
      await collectionsApi.create(backendData);
      handleClose();
      onCollectionCreated?.();
      showToast('Collection created successfully.', 'success');
    } catch (error) {
      console.error('Failed to create collection:', error);
      showToast('Failed to create collection. Please try again.', 'error');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <>
      <button 
        className="add-collection-btn"
        onClick={() => setIsOpen(true)}
      >
        <Plus size={20} />
        <span>Add collection</span>
      </button>

      {isOpen && (
        <div className="modal-overlay" onClick={handleClose}>
          <div className="modal-content collection-form-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Create New Collection</h2>
              <button
                type="button"
                className="modal-close-btn"
                onClick={handleClose}
                disabled={isCreating}
                aria-label="Close"
              >
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="collection-form">
              {/* General Section */}
              <div className="form-section">
                <h3 className="section-title">General</h3>
                <div className="form-group">
                  <label htmlFor="title">Name</label>
                  <input
                    ref={titleInputRef}
                    id="title"
                    type="text"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    placeholder="Enter collection name"
                    required
                    disabled={isCreating}
                    maxLength={100}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="description">Description</label>
                  <textarea
                    id="description"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Enter collection description"
                    rows={4}
                    disabled={isCreating}
                    maxLength={1000}
                  />
                </div>
              </div>

              {/* Index Types Section */}
              <div className="form-section">
                <h3 className="section-title">Index Types</h3>
                <p className="section-description">
                  Select the AI capabilities you need, we will build corresponding indexes for your documents
                </p>
                <div className="index-types-list">
                  {INDEX_TYPES.map((indexType) => {
                    const indexTypes = formData.config?.indexTypes || {};
                    const isEnabled = indexTypes[indexType.id as keyof typeof indexTypes] ?? false;
                    return (
                      <div key={indexType.id} className="index-type-item">
                        <div className="index-type-header">
                          <div className="index-type-info">
                            <div className="index-type-name-row">
                              <span className="index-type-name">{indexType.name}</span>
                              {indexType.required && (
                                <span className="index-type-badge required">Required</span>
                              )}
                            </div>
                            <p className="index-type-description">{indexType.description}</p>
                          </div>
                          <label className="toggle-switch">
                            <input
                              type="checkbox"
                              checked={isEnabled}
                              onChange={() => handleIndexTypeToggle(indexType.id)}
                              disabled={indexType.required || isCreating}
                            />
                            <span className="toggle-slider"></span>
                          </label>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Model Settings Section */}
              <div className="form-section">
                <h3 className="section-title">Model Settings</h3>
                <p className="section-description">
                  Select AI models for document processing. Different index types require different model support.
                </p>
                <div className="form-group">
                  <label htmlFor="embedding-model">Embedding Model</label>
                  <select
                    id="embedding-model"
                    value={formData.config?.embeddingModel || embeddingModels[0] || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: {
                          ...formData.config,
                          embeddingModel: e.target.value,
                        },
                      })
                    }
                    disabled={isCreating || modelsLoading}
                    className="form-select"
                  >
                    {modelsLoading ? (
                      <option value="">Loading models...</option>
                    ) : (
                      embeddingModels.map((model) => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))
                    )}
                  </select>
                  <p className="field-description">
                    An embedding model translates data into numerical vectors that capture their semantic meaning and relationships.
                  </p>
                </div>
                <div className="form-group">
                  <label htmlFor="completion-model">Completion Model</label>
                  <select
                    id="completion-model"
                    value={formData.config?.completionModel || completionModels[0] || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: {
                          ...formData.config,
                          completionModel: e.target.value,
                        },
                      })
                    }
                    disabled={isCreating || modelsLoading}
                    className="form-select"
                  >
                    {modelsLoading ? (
                      <option value="">Loading models...</option>
                    ) : (
                      completionModels.map((model) => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))
                    )}
                  </select>
                  <p className="field-description">
                    A completion model is an AI that generates new content by predicting the most likely subsequent text based on a given input.
                  </p>
                </div>
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleClose}
                  disabled={isCreating}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={isCreating || !formData.title?.trim()}
                >
                  {isCreating ? 'Creating...' : 'Create Collection'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
