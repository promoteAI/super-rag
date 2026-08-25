import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { ArrowLeft, Search, Plus, MoreVertical, Trash2, RotateCw, UploadCloud, Globe, User, Star } from 'lucide-react';
import { collectionsApi, marketplaceApi } from '../api/client';
import type { Collection, Document, SharedCollection } from '../types';
import { formatDistanceToNow } from 'date-fns';
import { showToast } from '../utils/toast';
import DocumentUpload from '../components/DocumentUpload';
import CollectionSettingsForm from '../components/CollectionSettingsForm';
import KnowledgeGraphView from '../components/KnowledgeGraphView';
import ConfirmDialog from '../components/ConfirmDialog';
import './CollectionDetailPage.css';

export default function CollectionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const isMarketplace = location.pathname.startsWith('/marketplace/collections');
  const [collection, setCollection] = useState<Collection | SharedCollection | null>(null);
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'documents' | 'knowledge-graph' | 'evaluations' | 'settings'>('documents');
  const [rebuildDialogDoc, setRebuildDialogDoc] = useState<Document | null>(null);
  const [rebuildIndexTypes, setRebuildIndexTypes] = useState({
    vectorAndFulltext: true,
    graph: true,
    summary: true,
    vision: true,
  });
  const [isRebuildingIndexes, setIsRebuildingIndexes] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deletingDoc, setDeletingDoc] = useState<Document | null>(null);
  const [isPublishing, setIsPublishing] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [headerMenuOpen, setHeaderMenuOpen] = useState(false);
  const headerMenuRef = useRef<HTMLDivElement>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ [key: string]: { position: 'bottom' | 'top'; top: number; right: number } }>({});

  const loadCollection = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      const data = isMarketplace
        ? await marketplaceApi.getCollection(id)
        : await collectionsApi.get(id);
      setCollection(data);
    } catch (error) {
      console.error('Failed to load collection:', error);
      alert('Failed to load collection. Please try again.');
      navigate(isMarketplace ? '/marketplace' : '/collections');
    } finally {
      setLoading(false);
    }
  }, [id, navigate, isMarketplace]);

  const loadDocuments = useCallback(async () => {
    if (!id) return;
    try {
      setDocumentsLoading(true);
      const data = isMarketplace
        ? await marketplaceApi.getDocuments(id, 1, 20, searchQuery || undefined)
        : await collectionsApi.getDocuments(id, 1, 20, searchQuery || undefined);
      const docs = data.items || [];
      
      // 映射字段名（后端返回的字段名与前端期望的不同）
      const mappedDocs = docs.map((doc: any) => {
        // 处理合并的 vector_and_fulltext_index_status 字段
        const vectorAndFulltextStatus = doc.vector_and_fulltext_index_status || 
                                        doc.vector_and_fulltext_status ||
                                        doc.vectorAndFulltextStatus;
        
        return {
          ...doc,
          // 文件名映射：后端返回 name，前端期望 file_name
          file_name: doc.name || doc.file_name || doc.filename || '',
          // 文件大小映射：后端返回 size，前端期望 file_size
          file_size: doc.size || doc.file_size || doc.fileSize || 0,
          // 状态字段映射：后端返回 vector_and_fulltext_index_status（合并字段），映射到 vector_status 用于显示
          vector_status: vectorAndFulltextStatus || 
                        doc.vector_index_status || 
                        doc.vector_status || 
                        doc.vectorStatus,
          // 保留 fulltext_status 映射以保持向后兼容性（虽然现在不再单独显示）
          fulltext_status: vectorAndFulltextStatus || 
                          doc.fulltext_index_status || 
                          doc.fulltext_status || 
                          doc.fulltextStatus,
          graph_status: doc.graph_index_status || 
                       doc.graph_status || 
                       doc.graphStatus,
          summary_status: doc.summary_index_status || 
                         doc.summary_status || 
                         doc.summaryStatus,
          vision_status: doc.vision_index_status || 
                       doc.vision_status || 
                       doc.visionStatus,
        };
      });
      
      setDocuments(mappedDocs);
      // 如果没有文档且不在搜索状态，自动显示上传界面（市场模式不显示上传）
      if (!searchQuery) {
        setShowUpload(mappedDocs.length === 0 && !isMarketplace);
      }
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setDocumentsLoading(false);
    }
  }, [id, searchQuery, isMarketplace]);

  useEffect(() => {
    loadCollection();
  }, [loadCollection]);

  useEffect(() => {
    if (activeTab === 'documents') {
      loadDocuments();
    }
  }, [activeTab, loadDocuments]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (target.closest('.table-action-menu') || target.closest('.action-button')) {
        return;
      }
      setOpenMenuId(null);
    };
    
    const handleScroll = () => {
      setOpenMenuId(null);
    };
    
    const handleResize = () => {
      setOpenMenuId(null);
    };
    
    document.addEventListener('click', handleClickOutside);
    window.addEventListener('scroll', handleScroll, true);
    window.addEventListener('resize', handleResize);
    
    return () => {
      document.removeEventListener('click', handleClickOutside);
      window.removeEventListener('scroll', handleScroll, true);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Unknown';
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true });
    } catch {
      return 'Unknown';
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const getStatusBadge = (status?: string) => {
    if (!status) return { text: 'Unknown', class: 'status-unknown' };
    const statusLower = status.toLowerCase();
    if (statusLower === 'active' || statusLower === 'success' || statusLower === 'completed' || statusLower === 'complete') {
      return { text: 'Active', class: 'status-active' };
    } else if (statusLower === 'failed' || statusLower === 'error') {
      return { text: 'Failed', class: 'status-failed' };
    } else if (statusLower === 'processing' || statusLower === 'pending' || statusLower === 'creating') {
      return { text: 'Processing', class: 'status-processing' };
    } else if (statusLower === 'skipped') {
      return { text: 'Skipped', class: 'status-unknown' };
    }
    return { text: status, class: 'status-unknown' };
  };

  const isSharedCollection = (c: Collection | SharedCollection | null): c is SharedCollection =>
    c != null && 'owner_user_id' in c;
  const isPublic = isSharedCollection(collection) ? true : Boolean((collection as Collection)?.is_published);
  const status = (collection as Collection)?.status ?? 'ACTIVE';
  const statusLabel = status === 'INACTIVE' ? 'Inactive' : status === 'DELETED' ? 'Deleted' : 'Active';
  const statusClass = status === 'INACTIVE' ? 'inactive' : status === 'DELETED' ? 'deleted' : 'active';
  const updatedText = isSharedCollection(collection)
    ? formatDate(collection.gmt_subscribed ?? undefined)
    : formatDate((collection as Collection)?.updated || (collection as Collection)?.created);

  const handleSubscribe = async () => {
    if (!id || isSubscribing) return;
    try {
      setIsSubscribing(true);
      const updated = await marketplaceApi.subscribe(id);
      setCollection(updated);
      showToast('订阅成功。', 'success');
    } catch (error) {
      console.error('Failed to subscribe:', error);
      const message = error instanceof Error ? error.message : '订阅失败，请重试。';
      showToast(message, 'error');
    } finally {
      setIsSubscribing(false);
    }
  };

  const handleUnsubscribe = async () => {
    if (!id || isSubscribing) return;
    try {
      setIsSubscribing(true);
      await marketplaceApi.unsubscribe(id);
      await loadCollection();
      showToast('已取消订阅。', 'success');
    } catch (error) {
      console.error('Failed to unsubscribe:', error);
      const message = error instanceof Error ? error.message : '取消订阅失败，请重试。';
      showToast(message, 'error');
    } finally {
      setIsSubscribing(false);
    }
  };

  // 根据集合配置决定哪些索引类型启用
  const collectionConfig: any = (collection as any)?.config || {};
  const enableVectorAndFulltext = collectionConfig.enable_vector_and_fulltext === true;
  const enableKnowledgeGraph = collectionConfig.enable_knowledge_graph === true;
  const enableSummary = collectionConfig.enable_summary === true;
  const enableVision = collectionConfig.enable_vision === true;

  useEffect(() => {
    if (!headerMenuOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (headerMenuRef.current && !headerMenuRef.current.contains(e.target as Node)) {
        setHeaderMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [headerMenuOpen]);

  const handleDeleteClick = () => {
    setHeaderMenuOpen(false);
    if (!collection?.id || isDeleting) return;
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = async () => {
    if (!collection?.id) return;
    try {
      setIsDeleting(true);
      await collectionsApi.delete(collection.id);
      setShowDeleteConfirm(false);
      navigate('/collections');
    } catch (error) {
      console.error('Failed to delete collection:', error);
      showToast('Delete failed. Please try again.', 'error');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleTogglePublish = async () => {
    setHeaderMenuOpen(false);
    if (!collection?.id || isPublishing) return;
    const nextPublished = !isPublic;
    try {
      setIsPublishing(true);
      if (nextPublished) {
        await collectionsApi.publish(collection.id);
      } else {
        await collectionsApi.unpublish(collection.id);
      }
      await loadCollection();
      showToast(
        nextPublished ? 'Published to Marketplace.' : 'Unpublished from Marketplace.',
        'success',
      );
    } catch (error) {
      console.error('Failed to toggle publish status:', error);
      showToast('Operation failed. Please try again.', 'error');
    } finally {
      setIsPublishing(false);
    }
  };

  const handleToggleMenu = (event: React.MouseEvent<HTMLButtonElement>, docId?: string) => {
    event.stopPropagation();
    if (!docId) {
      return;
    }
    
    const isOpening = openMenuId !== docId;
    if (isOpening) {
      // 检测菜单应该向上还是向下展开
      const button = event.currentTarget;
      const rect = button.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const menuHeight = 90; // 估算菜单高度（2个菜单项 + padding）
      const spaceBelow = viewportHeight - rect.bottom;
      const spaceAbove = rect.top;
      
      // 如果下方空间不足但上方空间足够，则向上展开
      const position = spaceBelow < menuHeight && spaceAbove > spaceBelow ? 'top' : 'bottom';
      
      // 计算菜单位置（使用 fixed 定位）
      const top = position === 'bottom' ? rect.bottom + 6 : rect.top - menuHeight - 6;
      const right = window.innerWidth - rect.right;
      
      setMenuPosition((prev) => ({ 
        ...prev, 
        [docId]: { position, top, right } 
      }));
    }
    
    setOpenMenuId((prev) => (prev === docId ? null : docId));
  };

  const handleDeleteDocumentClick = (event: React.MouseEvent<HTMLButtonElement>, doc: Document) => {
    event.stopPropagation();
    setOpenMenuId(null);
    setDeletingDoc(doc);
  };

  const handleConfirmDeleteDocument = async () => {
    if (!id || !deletingDoc?.id) {
      return;
    }
    try {
      setIsDeleting(true);
      await collectionsApi.deleteDocument(id, deletingDoc.id);
      setDeletingDoc(null);
      await loadDocuments();
      showToast('Document deleted successfully.', 'success');
    } catch (error) {
      console.error('Failed to delete document:', error);
      showToast('Delete failed. Please try again.', 'error');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleOpenRebuildDialog = (event: React.MouseEvent<HTMLButtonElement>, doc: Document) => {
    event.stopPropagation();
    setOpenMenuId(null);
    setRebuildDialogDoc(doc);
    setRebuildIndexTypes({
      vectorAndFulltext: enableVectorAndFulltext,
      graph: enableKnowledgeGraph,
      summary: enableSummary,
      vision: enableVision,
    });
  };

  const handleCloseRebuildDialog = () => {
    if (isRebuildingIndexes) {
      return;
    }
    setRebuildDialogDoc(null);
  };

  const handleConfirmRebuildIndexes = async () => {
    if (!id || !rebuildDialogDoc?.id) {
      return;
    }

    const selectedTypes: string[] = [];
    if (rebuildIndexTypes.vectorAndFulltext) {
      selectedTypes.push('VECTOR_AND_FULLTEXT');
    }
    if (rebuildIndexTypes.graph) {
      selectedTypes.push('GRAPH');
    }
    if (rebuildIndexTypes.summary) {
      selectedTypes.push('SUMMARY');
    }
    if (rebuildIndexTypes.vision) {
      selectedTypes.push('VISION');
    }

    if (selectedTypes.length === 0) {
      showToast('Please select at least one index type to rebuild.', 'error');
      return;
    }

    try {
      setIsRebuildingIndexes(true);
      await collectionsApi.rebuildDocumentIndex(id, rebuildDialogDoc.id, selectedTypes);
      showToast('Rebuild index request submitted successfully.', 'success');
      await loadDocuments();
    } catch (error) {
      console.error('Failed to rebuild index:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      showToast(`Rebuild index failed: ${errorMessage}`, 'error');
    } finally {
      setIsRebuildingIndexes(false);
      setRebuildDialogDoc(null);
    }
  };

  const handleRebuildFailedIndexes = async () => {
    if (!id) {
      return;
    }
    try {
      setIsRebuildingIndexes(true);
      await collectionsApi.rebuildFailedIndexes(id);
      showToast('Rebuild failed indexes request submitted successfully.', 'success');
      // 刷新文档列表以查看更新的状态
      await loadDocuments();
    } catch (error) {
      console.error('Failed to rebuild failed indexes:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      showToast(`Rebuild failed indexes failed: ${errorMessage}`, 'error');
    } finally {
      setIsRebuildingIndexes(false);
    }
  };

  if (loading) {
    return (
      <div className="collection-detail-page">
        <div className="loading-state">Loading...</div>
      </div>
    );
  }

  if (!collection) {
    return (
      <div className="collection-detail-page">
        <div className="error-state">Collection not found</div>
      </div>
    );
  }

  return (
    <div className="collection-detail-page">
      <div className="breadcrumb">
        <Link to={isMarketplace ? '/marketplace' : '/collections'} className="breadcrumb-link">
          {isMarketplace ? 'Marketplace' : 'Collections'}
        </Link>
        <span className="breadcrumb-separator">/</span>
        <span className="breadcrumb-current">
          {activeTab === 'documents' ? (showUpload && !isMarketplace ? 'Documents > Upload' : 'Documents') : activeTab}
        </span>
      </div>

      <div className="collection-header">
        <div className="collection-header-content">
          <div className="collection-title-row">
            <h1 className="collection-title">{collection.title || 'Untitled'}</h1>
            <span className={`privacy-badge ${isPublic ? 'public' : 'private'}`}>
              {isPublic ? 'Public' : 'Private'}
            </span>
          </div>
          <div className="collection-meta">
            <span className="collection-updated">{updatedText}</span>
            <span className={`collection-status ${statusClass}`}>{statusLabel}</span>
          </div>
          <p className="collection-description">
            {collection.description || 'No description provided.'}
          </p>
        </div>
        <div className="collection-header-actions">
          {isMarketplace && isSharedCollection(collection) && (
            <>
              <div className="collection-owner">
                <User size={16} />
                <span className="collection-owner-label">所属人</span>
                <span>{collection.owner_username ?? 'Unknown'}</span>
              </div>
              {!(
                collection.owner_user_id &&
                String(collection.owner_user_id) === String(localStorage.getItem('user_id') || '')
              ) && (
                <button
                  type="button"
                  className={`subscribe-button ${collection.subscription_id ? 'subscribed' : ''}`}
                  onClick={collection.subscription_id ? handleUnsubscribe : handleSubscribe}
                  disabled={isSubscribing}
                >
                  <Star size={16} fill={collection.subscription_id ? 'currentColor' : 'none'} />
                  <span>{isSubscribing ? '...' : collection.subscription_id ? 'Subscribed' : 'Subscribe'}</span>
                </button>
              )}
            </>
          )}
          {!isMarketplace && (
          <div className="header-menu-wrapper" ref={headerMenuRef}>
            <button
              className="header-menu-btn"
              type="button"
              onClick={() => setHeaderMenuOpen((v) => !v)}
              aria-label="More options"
              title="More options"
            >
              <MoreVertical size={20} />
            </button>
            {headerMenuOpen && (
              <div className="header-dropdown-menu">
                <button
                  type="button"
                  className="header-dropdown-item"
                  onClick={handleTogglePublish}
                  disabled={isPublishing}
                >
                  {isPublic ? <Globe size={16} /> : <UploadCloud size={16} />}
                  <div className="header-dropdown-item-content">
                    <span className="header-dropdown-item-title">
                      {isPublic ? 'Unpublish from Marketplace' : 'Publish to Marketplace'}
                    </span>
                    <span className="header-dropdown-item-desc">
                      {isPublic
                        ? 'Remove the collection from the marketplace, making it private.'
                        : 'Share this collection publicly on the marketplace.'}
                    </span>
                  </div>
                </button>
                <button
                  type="button"
                  className="header-dropdown-item danger"
                  onClick={handleDeleteClick}
                  disabled={isDeleting}
                >
                  <Trash2 size={16} />
                  <div className="header-dropdown-item-content">
                    <span className="header-dropdown-item-title">Delete Collection</span>
                  </div>
                </button>
              </div>
            )}
          </div>
          )}
          <button
            className="back-button"
            onClick={() => navigate(isMarketplace ? '/marketplace' : '/collections')}
            aria-label="Back"
            title="Back"
          >
            <ArrowLeft size={20} />
          </button>
        </div>
      </div>

      <div className="collection-tabs">
        <button
          className={`tab-button ${activeTab === 'documents' ? 'active' : ''}`}
          onClick={() => setActiveTab('documents')}
        >
          Documents
        </button>
        <button
          className={`tab-button ${activeTab === 'knowledge-graph' ? 'active' : ''}`}
          onClick={() => setActiveTab('knowledge-graph')}
        >
          Knowledge Graph
        </button>
        {!isMarketplace && (
          <>
            <button
              className={`tab-button ${activeTab === 'evaluations' ? 'active' : ''}`}
              onClick={() => setActiveTab('evaluations')}
            >
              Evaluations
            </button>
            <button
              className={`tab-button ${activeTab === 'settings' ? 'active' : ''}`}
              onClick={() => setActiveTab('settings')}
            >
              Settings
            </button>
          </>
        )}
      </div>

      {activeTab === 'documents' && (
        <div className="documents-section">
          {!showUpload && (
            <div className="documents-controls">
              <div className="search-wrapper">
                <Search size={18} className="search-icon" />
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search documents"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              {!isMarketplace && (
                <div className="controls-actions">
                  <button 
                    className="rebuild-failed-button"
                    onClick={handleRebuildFailedIndexes}
                    title="Rebuild failed indexes"
                    disabled={isRebuildingIndexes}
                  >
                    <RotateCw size={18} />
                    <span>Rebuild Failed Index</span>
                  </button>
                  <button 
                    className="add-documents-button"
                    onClick={() => setShowUpload(true)}
                  >
                    <Plus size={18} />
                    <span>Add Documents</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {showUpload && !isMarketplace ? (
            <div className="upload-section">
              {documents.length > 0 && (
                <button 
                  className="back-to-list-button"
                  onClick={() => setShowUpload(false)}
                >
                  <ArrowLeft size={18} />
                  <span>Back to Documents</span>
                </button>
              )}
              <DocumentUpload
                collectionId={id || ''}
                onUploadSuccess={() => {
                  setShowUpload(false);
                  loadDocuments();
                }}
              />
            </div>
          ) : documents.length > 0 ? (
            <div className="documents-table-wrapper">
              {documentsLoading ? (
                <div className="loading-state">Loading documents...</div>
              ) : (
                <div className="table-container">
                  <table className="documents-table">
                    <thead>
                      <tr>
                        {!isMarketplace && (
                          <th>
                            <input type="checkbox" />
                          </th>
                        )}
                        <th>File</th>
                        {enableVectorAndFulltext && <th>Vector &amp; Fulltext</th>}
                        {enableKnowledgeGraph && <th>Graph</th>}
                        {enableSummary && <th>Summary</th>}
                        {enableVision && <th>Vision</th>}
                        <th>Last Updated</th>
                        {!isMarketplace && <th></th>}
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((doc) => {
                        // 使用 vector_status（已从 vector_and_fulltext_index_status 映射）
                        const vectorAndFulltextStatus = getStatusBadge(doc.vector_status);
                        const graphStatus = getStatusBadge(doc.graph_status);
                        const summaryStatus = getStatusBadge(doc.summary_status);
                        const visionStatus = getStatusBadge(doc.vision_status);

                        return (
                          <tr key={doc.id || Math.random()}>
                            {!isMarketplace && (
                              <td>
                                <input type="checkbox" />
                              </td>
                            )}
                            <td>
                              <div className="file-info">
                                <span className="file-name">{doc.file_name || 'Unknown'}</span>
                                <span className="file-size">{formatFileSize(doc.file_size)}</span>
                              </div>
                            </td>
                            {enableVectorAndFulltext && (
                              <td>
                                <span className={`status-badge ${vectorAndFulltextStatus.class}`}>
                                  {vectorAndFulltextStatus.text}
                                </span>
                              </td>
                            )}
                            {enableKnowledgeGraph && (
                              <td>
                                <span className={`status-badge ${graphStatus.class}`}>
                                  {graphStatus.text}
                                </span>
                              </td>
                            )}
                            {enableSummary && (
                              <td>
                                <span className={`status-badge ${summaryStatus.class}`}>
                                  {summaryStatus.text}
                                </span>
                              </td>
                            )}
                            {enableVision && (
                              <td>
                                <span className={`status-badge ${visionStatus.class}`}>
                                  {visionStatus.text}
                                </span>
                              </td>
                            )}
                            <td className="last-updated">{formatDate(doc.updated || doc.created)}</td>
                            {!isMarketplace && (
                              <td className="table-actions-cell">
                                <div className="table-actions">
                                  <button
                                    className="action-button"
                                    title="More options"
                                    type="button"
                                    onClick={(event) => handleToggleMenu(event, doc.id)}
                                  >
                                    <MoreVertical size={16} />
                                  </button>
                                  {openMenuId === doc.id && menuPosition[doc.id || ''] && (
                                    <div
                                      className={`table-action-menu ${
                                        menuPosition[doc.id || '']?.position === 'top' ? 'menu-top' : ''
                                      }`}
                                      style={{
                                        position: 'fixed',
                                        top: `${menuPosition[doc.id || '']?.top}px`,
                                        right: `${menuPosition[doc.id || '']?.right}px`,
                                      }}
                                    >
                                      <button
                                        type="button"
                                        className="menu-item"
                                        onClick={(event) => handleOpenRebuildDialog(event, doc)}
                                      >
                                        <RotateCw size={16} />
                                        <span>Rebuild Indexes</span>
                                      </button>
                                      <button
                                        type="button"
                                        className="menu-item danger"
                                        onClick={(event) => handleDeleteDocumentClick(event, doc)}
                                      >
                                        <Trash2 size={16} />
                                        <span>Delete document</span>
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </td>
                            )}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state">No documents in this collection.</div>
          )}

          {!showUpload && documents.length > 0 && (
            <div className="table-footer">
              {!isMarketplace && (
                <span className="selection-info">0 of {documents.length} row(s) selected.</span>
              )}
              <div className="pagination">
                <span>Rows per page 20</span>
                <span>Page 1 of 1</span>
                <div className="pagination-buttons">
                  <button disabled>‹</button>
                  <button disabled>‹‹</button>
                  <button disabled>›</button>
                  <button disabled>››</button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'knowledge-graph' && id && (
        <KnowledgeGraphView collectionId={id} />
      )}

      {activeTab === 'evaluations' && (
        <div className="tab-content">
          <div className="empty-state">Evaluations content coming soon...</div>
        </div>
      )}

      {activeTab === 'settings' && (
        <div className="tab-content settings-content">
          {collection && (
            <CollectionSettingsForm
              collection={collection}
              onUpdated={() => {
                loadCollection();
              }}
            />
          )}
        </div>
      )}
      {rebuildDialogDoc && (
        <div className="rebuild-index-modal-backdrop" onClick={handleCloseRebuildDialog}>
          <div
            className="rebuild-index-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="rebuild-index-modal-header">
              <h2 className="rebuild-index-modal-title">Rebuild Indexes</h2>
              <p className="rebuild-index-modal-subtitle">
                {rebuildDialogDoc.file_name || 'Unknown'}
              </p>
            </div>
            <div className="rebuild-index-modal-body">
              <p className="rebuild-index-modal-description">
                Select which index types you want to rebuild for this document.
              </p>
              <div className="rebuild-index-options">
                {enableVectorAndFulltext && (
                  <label className="rebuild-index-option">
                    <input
                      type="checkbox"
                      checked={rebuildIndexTypes.vectorAndFulltext}
                      onChange={(event) =>
                        setRebuildIndexTypes((prev) => ({
                          ...prev,
                          vectorAndFulltext: event.target.checked,
                        }))
                      }
                    />
                    <div className="rebuild-index-option-content">
                      <span className="rebuild-index-option-title">Vector &amp; Fulltext</span>
                      <span className="rebuild-index-option-description">
                        Represents text as high-dimensional vectors and enables keyword search.
                      </span>
                    </div>
                  </label>
                )}
                {enableKnowledgeGraph && (
                  <label className="rebuild-index-option">
                    <input
                      type="checkbox"
                      checked={rebuildIndexTypes.graph}
                      onChange={(event) =>
                        setRebuildIndexTypes((prev) => ({
                          ...prev,
                          graph: event.target.checked,
                        }))
                      }
                    />
                    <div className="rebuild-index-option-content">
                      <span className="rebuild-index-option-title">Graph</span>
                      <span className="rebuild-index-option-description">
                        Stores entities and relationships for knowledge graph queries.
                      </span>
                    </div>
                  </label>
                )}
                {enableSummary && (
                  <label className="rebuild-index-option">
                    <input
                      type="checkbox"
                      checked={rebuildIndexTypes.summary}
                      onChange={(event) =>
                        setRebuildIndexTypes((prev) => ({
                          ...prev,
                          summary: event.target.checked,
                        }))
                      }
                    />
                    <div className="rebuild-index-option-content">
                      <span className="rebuild-index-option-title">Summary</span>
                      <span className="rebuild-index-option-description">
                        Indexes summaries or metadata for faster retrieval.
                      </span>
                    </div>
                  </label>
                )}
                {enableVision && (
                  <label className="rebuild-index-option">
                    <input
                      type="checkbox"
                      checked={rebuildIndexTypes.vision}
                      onChange={(event) =>
                        setRebuildIndexTypes((prev) => ({
                          ...prev,
                          vision: event.target.checked,
                        }))
                      }
                    />
                    <div className="rebuild-index-option-content">
                      <span className="rebuild-index-option-title">Vision</span>
                      <span className="rebuild-index-option-description">
                        Encodes images and other visual content into feature vectors.
                      </span>
                    </div>
                  </label>
                )}
              </div>
            </div>
            <div className="rebuild-index-modal-footer">
              <button
                type="button"
                className="rebuild-index-modal-button secondary"
                onClick={handleCloseRebuildDialog}
                disabled={isRebuildingIndexes}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rebuild-index-modal-button primary"
                onClick={handleConfirmRebuildIndexes}
                disabled={isRebuildingIndexes}
              >
                {isRebuildingIndexes ? 'Rebuilding...' : 'Continue'}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Are you absolutely sure?"
        description="This action cannot be undone. This will permanently delete collection and remove your documents from our servers."
        confirmText="Continue"
        loading={isDeleting}
        onCancel={() => setShowDeleteConfirm(false)}
        onConfirm={handleDeleteConfirm}
      />

      <ConfirmDialog
        open={Boolean(deletingDoc)}
        title="Delete this document?"
        description={
          deletingDoc
            ? `This action cannot be undone. This will permanently delete "${deletingDoc.file_name || deletingDoc.name || 'Untitled'}" from this collection.`
            : ''
        }
        confirmText="Delete"
        loading={isDeleting}
        onCancel={() => setDeletingDoc(null)}
        onConfirm={handleConfirmDeleteDocument}
      />
    </div>
  );
}
