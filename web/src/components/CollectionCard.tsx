import { useMemo, useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { MoreVertical, Trash2, UploadCloud, Globe, Calendar, User } from 'lucide-react';
import type { CollectionView } from '../types';
import { formatDistanceToNow } from 'date-fns';
import { collectionsApi } from '../api/client';
import { showToast } from '../utils/toast';
import ConfirmDialog from './ConfirmDialog';
import './CollectionCard.css';

interface CollectionCardProps {
  collection: CollectionView;
  onDeleted?: () => void;
  /** 来自市场页面时，点击跳转到 /marketplace/collections/:id */
  fromMarketplace?: boolean;
  /** 市场浏览模式：简化卡片，仅标题+描述+作者，无徽章和状态 */
  marketplaceList?: boolean;
}

export default function CollectionCard({ collection, onDeleted, fromMarketplace, marketplaceList }: CollectionCardProps) {
  const navigate = useNavigate();
  const [isDeleting, setIsDeleting] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const formatDate = (dateString?: string) => {
    if (!dateString) return '';
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true });
    } catch {
      return '';
    }
  };

  const isPublic = Boolean(collection.is_published);
  const status = collection.status ?? 'ACTIVE';
  const statusLabel = status === 'INACTIVE' ? 'Inactive' : status === 'DELETED' ? 'Deleted' : 'Active';
  const statusClass = status === 'INACTIVE' ? 'inactive' : status === 'DELETED' ? 'deleted' : 'active';
  const hasDate = Boolean(collection.updated || collection.created);
  const updatedText = formatDate(collection.updated || collection.created);
  const ownerLabel = collection.owner_username;
  const avatarLabel = useMemo(() => {
    const trimmed = collection.title?.trim();
    return trimmed ? trimmed.charAt(0).toUpperCase() : 'C';
  }, [collection.title]);

  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpen]);

  const handleCardClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.closest('button') || target.closest('a') || target.closest('.card-dropdown-menu')) {
      return;
    }
    if (collection.id) {
      navigate(fromMarketplace ? `/marketplace/collections/${collection.id}` : `/collections/${collection.id}`);
    }
  };

  const handleDeleteClick = () => {
    setMenuOpen(false);
    if (!collection.id || isDeleting) return;
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = async () => {
    if (!collection.id) return;
    try {
      setIsDeleting(true);
      await collectionsApi.delete(collection.id);
      setShowDeleteConfirm(false);
      onDeleted?.();
    } catch (error) {
      console.error('Failed to delete collection', error);
      showToast('Delete failed. Please try again.', 'error');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleTogglePublish = async () => {
    setMenuOpen(false);
    if (!collection.id || isPublishing) return;
    try {
      setIsPublishing(true);
      if (isPublic) {
        await collectionsApi.unpublish(collection.id);
      } else {
        await collectionsApi.publish(collection.id);
      }
      onDeleted?.();
    } catch (error) {
      console.error('Failed to toggle publish status', error);
      showToast('Operation failed. Please try again.', 'error');
    } finally {
      setIsPublishing(false);
    }
  };

  /** 仅 Marketplace 浏览页使用简化卡片；Collections 页的订阅集合使用完整卡片（Subscribed 徽章 + Active） */
  const isMarketplaceList = marketplaceList === true;

  return (
    <div className={`collection-card ${isMarketplaceList ? 'collection-card--marketplace' : ''}`} onClick={handleCardClick}>
      <div className="card-header">
        <div className="card-identity">
          <div className="card-icon">
            <span>{avatarLabel}</span>
          </div>
          <div className="card-title-section">
            <div className="card-title-row">
              <h3 className="card-title">{collection.title || 'Untitled'}</h3>
              {!isMarketplaceList && (
                fromMarketplace ? (
                  <span className="privacy-badge subscribed">Subscribed</span>
                ) : (
                  <span className={`privacy-badge ${isPublic ? 'public' : 'private'}`}>
                    {isPublic ? 'Public' : 'Private'}
                  </span>
                )
              )}
            </div>
          </div>
        </div>
        {onDeleted && (
          <div className="card-actions" ref={menuRef}>
            <button
              className="card-action-btn"
              title="More options"
              type="button"
              onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
            >
              <MoreVertical size={16} />
            </button>
            {menuOpen && (
              <div className="card-dropdown-menu">
                <button
                  type="button"
                  className="card-dropdown-item"
                  onClick={(e) => { e.stopPropagation(); handleTogglePublish(); }}
                  disabled={isPublishing}
                >
                  {isPublic ? <Globe size={16} /> : <UploadCloud size={16} />}
                  <div className="card-dropdown-item-content">
                    <span className="card-dropdown-item-title">
                      {isPublic ? 'Unpublish from Marketplace' : 'Publish to Marketplace'}
                    </span>
                    <span className="card-dropdown-item-desc">
                      {isPublic
                        ? 'Remove the collection from the marketplace, making it private.'
                        : 'Share this collection publicly on the marketplace.'}
                    </span>
                  </div>
                </button>
                <button
                  type="button"
                  className="card-dropdown-item danger"
                  onClick={(e) => { e.stopPropagation(); handleDeleteClick(); }}
                  disabled={isDeleting}
                >
                  <Trash2 size={16} />
                  <div className="card-dropdown-item-content">
                    <span className="card-dropdown-item-title">Delete Collection</span>
                  </div>
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <p className="card-description">
        {collection.description || 'No description available.'}
      </p>

      <div className="card-footer">
        <div className="card-meta">
          {isMarketplaceList ? (
            <span className="card-owner">
              <User size={14} className="card-owner-icon" />
              {ownerLabel || '--'}
            </span>
          ) : (
            <>
              <span className="card-updated">
                <Calendar size={14} className="card-updated-icon" />
                {hasDate ? updatedText : ownerLabel ? `Owner ${ownerLabel}` : '--'}
              </span>
              <span className={`card-status ${statusClass}`}>{statusLabel}</span>
            </>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Are you absolutely sure?"
        description="This action cannot be undone. This will permanently delete collection and remove your documents from our servers."
        confirmText="Continue"
        loading={isDeleting}
        onCancel={() => setShowDeleteConfirm(false)}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
