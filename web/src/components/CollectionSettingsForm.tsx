import { useState, useEffect, useRef } from 'react';
import { collectionsApi, availableModelsApi } from '../api/client';
import type { Collection, CollectionUpdate, ModelConfig } from '../types';
import { showToast } from '../utils/toast';
import './CollectionSettingsForm.css';

interface CollectionSettingsFormProps {
  collection: Collection;
  onUpdated?: () => void;
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

export default function CollectionSettingsForm({ collection, onUpdated }: CollectionSettingsFormProps) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [embeddingModels, setEmbeddingModels] = useState<string[]>(DEFAULT_EMBEDDING_MODELS);
  const [completionModels, setCompletionModels] = useState<string[]>(DEFAULT_COMPLETION_MODELS);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [formData, setFormData] = useState<CollectionUpdate>({
    title: collection.title || '',
    description: collection.description || '',
    config: collection.config || {},
  });
  const titleInputRef = useRef<HTMLInputElement>(null);

  // 当 collection 更新时，同步表单数据
  useEffect(() => {
    const existingConfig = (collection.config as any) || {};

    // 从后端的 enable_* 字段推导前端使用的 indexTypes
    const derivedIndexTypes = {
      vectorAndFulltext:
        existingConfig.indexTypes?.vectorAndFulltext ??
        (existingConfig.enable_vector_and_fulltext !== false),
      graph:
        existingConfig.indexTypes?.graph ??
        (existingConfig.enable_knowledge_graph === true),
      summary:
        existingConfig.indexTypes?.summary ??
        (existingConfig.enable_summary === true),
      vision:
        existingConfig.indexTypes?.vision ??
        (existingConfig.enable_vision === true),
    };

    // 从后端的 embedding / completion 配置中抽取模型名
    const derivedEmbeddingModel =
      existingConfig.embeddingModel ||
      existingConfig.embedding?.model ||
      'text-embedding-v4';
    const derivedCompletionModel =
      existingConfig.completionModel ||
      existingConfig.completion?.model ||
      'google/gemini-2.5-flash';

    const config = {
      ...existingConfig,
      indexTypes: {
        ...derivedIndexTypes,
      },
      embeddingModel: derivedEmbeddingModel,
      completionModel: derivedCompletionModel,
    };

    setFormData({
      title: collection.title || '',
      description: collection.description || '',
      config,
    });
  }, [collection]);

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
        }
        
        if (completionList.length > 0) {
          setCompletionModels(completionList);
        }
      } catch (error) {
        console.error('Failed to load available models:', error);
        // 使用默认模型列表
      } finally {
        setModelsLoading(false);
      }
    };
    
    // 组件加载时获取可用模型
    loadAvailableModels();
  }, []);

  useEffect(() => {
    if (titleInputRef.current) {
      titleInputRef.current.focus();
    }
  }, []);

  const handleIndexTypeToggle = (indexId: string) => {
    const indexType = INDEX_TYPES.find((t) => t.id === indexId);
    if (indexType?.required) return; // 不能关闭必需的索引类型

    setFormData((prev) => {
      const currentConfig = (prev.config as any) || {};
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

    if (!collection.id) {
      console.error('Collection ID is missing');
      return;
    }

    try {
      setIsUpdating(true);
      const currentConfig = (formData.config as any) || {};
      const currentIndexTypes = currentConfig.indexTypes || {};

      // 将前端的 indexTypes / embeddingModel / completionModel 映射回后端的配置结构
      const updatedConfig: any = {
        ...currentConfig,
        enable_vector_and_fulltext:
          currentIndexTypes.vectorAndFulltext !== false,
        enable_knowledge_graph: !!currentIndexTypes.graph,
        enable_summary: !!currentIndexTypes.summary,
        enable_vision: !!currentIndexTypes.vision,
        embedding: {
          ...(currentConfig.embedding || {}),
          model: currentConfig.embeddingModel || 'text-embedding-v4',
        },
        completion: {
          ...(currentConfig.completion || {}),
          model: currentConfig.completionModel || 'google/gemini-2.5-flash',
        },
      };

      // 这些是仅供前端使用的字段，不需要直接传给后端
      delete updatedConfig.indexTypes;
      delete updatedConfig.embeddingModel;
      delete updatedConfig.completionModel;

      await collectionsApi.update(collection.id, {
        ...formData,
        config: updatedConfig,
      });
      onUpdated?.();
      showToast('Update successfully.', 'success');
    } catch (error) {
      console.error('Failed to update collection:', error);
      showToast('Failed to update collection. Please try again.', 'error');
    } finally {
      setIsUpdating(false);
    }
  };

  const configForView = (formData.config as any) || {};
  const indexTypes = configForView.indexTypes || {};
  const embeddingModel =
    configForView.embeddingModel ||
    configForView.embedding?.model ||
    'text-embedding-v4';
  const completionModel =
    configForView.completionModel ||
    configForView.completion?.model ||
    'google/gemini-2.5-flash';

  return (
    <form onSubmit={handleSubmit} className="collection-settings-form">
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
            disabled={isUpdating}
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
            disabled={isUpdating}
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
                      disabled={indexType.required || isUpdating}
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
            value={embeddingModel}
            onChange={(e) =>
              setFormData({
                ...formData,
                config: {
                  ...formData.config,
                  embeddingModel: e.target.value,
                },
              })
            }
            disabled={isUpdating || modelsLoading}
            className="form-select"
          >
            {modelsLoading ? (
              <option value={embeddingModel}>Loading models...</option>
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
            value={completionModel}
            onChange={(e) =>
              setFormData({
                ...formData,
                config: {
                  ...formData.config,
                  completionModel: e.target.value,
                },
              })
            }
            disabled={isUpdating || modelsLoading}
            className="form-select"
          >
            {modelsLoading ? (
              <option value={completionModel}>Loading models...</option>
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

      <div className="form-actions">
        <button
          type="submit"
          className="btn-primary"
          disabled={isUpdating || !formData.title?.trim()}
        >
          {isUpdating ? 'Updating...' : 'Update Collection'}
        </button>
      </div>
    </form>
  );
}
