import { useState, useEffect, useMemo, useCallback } from 'react';
import { modelProvidersApi } from '../api/client';
import type { ModelProviderView } from '../types';
import { Plus, Search, MoreVertical } from 'lucide-react';
import './ProvidersPage.css';

export default function ProvidersPage() {
  const [providers, setProviders] = useState<ModelProviderView[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);
  const [showAddModal, setShowAddModal] = useState(false);

  const loadProviders = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage('');
      const data = await modelProvidersApi.list(currentPage, pageSize);
      setProviders(data.items || []);
      setTotalCount(data.pageResult?.count || 0);
    } catch (error) {
      console.error('Failed to load model providers:', error);
      setErrorMessage('加载模型供应商失败，请刷新重试。');
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize]);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  const handleSearch = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  }, []);

  const filteredProviders = useMemo(() => {
    if (!searchQuery) return providers;
    const query = searchQuery.toLowerCase();
    return providers.filter((provider) => (
      provider.name?.toLowerCase().includes(query) ||
      provider.api_base_url?.toLowerCase().includes(query)
    ));
  }, [providers, searchQuery]);

  const handleToggleEnabled = useCallback(async (providerId: string, enabled: boolean) => {
    try {
      await modelProvidersApi.toggleEnabled(providerId, !enabled);
      await loadProviders();
    } catch (error) {
      console.error('Failed to toggle provider status:', error);
      alert('切换供应商状态失败，请重试。');
    }
  }, [loadProviders]);

  const totalPages = Math.ceil(totalCount / pageSize);

  return (
    <div className="providers-page">
      <div className="page-header">
        <div className="page-header-content">
          <h1 className="page-title">模型供应商</h1>
          <p className="page-description">
            在此模块连接并定制您好的大型语言模型（LLM）供应商和模型。通过设置API密钥、选择模型及调整参数来提升AI使用体验。
          </p>
        </div>
      </div>

      <div className="page-content">
        <div className="page-controls">
          <div className="search-wrapper">
            <div className="search-input-container">
              <Search size={18} className="search-icon" />
              <input
                type="text"
                placeholder="搜索模型供应商"
                value={searchQuery}
                onChange={handleSearch}
                className="search-input"
              />
            </div>
          </div>
          <button 
            className="add-provider-btn"
            onClick={() => setShowAddModal(true)}
          >
            <Plus size={18} />
            <span>添加供应商</span>
          </button>
        </div>

        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <span>加载中...</span>
          </div>
        ) : errorMessage ? (
          <div className="error-state">{errorMessage}</div>
        ) : filteredProviders.length === 0 ? (
          <div className="empty-state">
            {searchQuery ? '未找到匹配的模型供应商。' : '暂无模型供应商，点击"添加供应商"创建第一个！'}
          </div>
        ) : (
          <>
            <div className="providers-table-container">
              <table className="providers-table">
                <thead>
                  <tr>
                    <th>
                      <input type="checkbox" className="table-checkbox" />
                    </th>
                    <th>名称</th>
                    <th>API地址</th>
                    <th>模型数量</th>
                    <th>可见范围</th>
                    <th>启用状态</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProviders.map((provider) => (
                    <tr key={provider.id}>
                      <td>
                        <input type="checkbox" className="table-checkbox" />
                      </td>
                      <td className="provider-name">{provider.name}</td>
                      <td className="provider-api">{provider.api_base_url}</td>
                      <td className="provider-count">{provider.model_count || 0}</td>
                      <td>
                        <span className={`visibility-badge ${provider.visibility?.toLowerCase()}`}>
                          {provider.visibility === 'PRIVATE' ? '私有' : '公开'}
                        </span>
                      </td>
                      <td>
                        <label className="toggle-switch">
                          <input
                            type="checkbox"
                            checked={provider.enabled}
                            onChange={() => handleToggleEnabled(provider.id!, provider.enabled!)}
                          />
                          <span className="toggle-slider"></span>
                        </label>
                      </td>
                      <td>
                        <button className="action-menu-btn">
                          <MoreVertical size={18} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <div className="pagination-info">
                {totalCount > 0 && (
                  <span>共{totalCount}条</span>
                )}
              </div>
              <div className="pagination-controls">
                <select 
                  className="page-size-select"
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setCurrentPage(1);
                  }}
                >
                  <option value="20">20</option>
                  <option value="50">50</option>
                  <option value="100">100</option>
                </select>
                <span className="page-info">
                  第{currentPage}页，共{totalPages}页
                </span>
                <div className="page-buttons">
                  <button
                    className="page-btn"
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                  >
                    «
                  </button>
                  <button
                    className="page-btn"
                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                  >
                    ‹
                  </button>
                  <button
                    className="page-btn"
                    onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                    disabled={currentPage === totalPages}
                  >
                    ›
                  </button>
                  <button
                    className="page-btn"
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage === totalPages}
                  >
                    »
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* 添加供应商模态框 - 暂时占位 */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>添加模型供应商</h2>
            <p>功能开发中...</p>
            <button onClick={() => setShowAddModal(false)}>关闭</button>
          </div>
        </div>
      )}
    </div>
  );
}
