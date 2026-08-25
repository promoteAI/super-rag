import { useState, useEffect, useMemo, useCallback } from 'react';
import { collectionsApi, marketplaceApi } from '../api/client';
import type { CollectionView } from '../types';
import CollectionCard from '../components/CollectionCard';
import SearchBar from '../components/SearchBar';
import AddCollectionButton from '../components/AddCollectionButton';
import LoadingSkeleton from '../components/LoadingSkeleton';
import './CollectionsPage.css';

function mapSharedToCollectionView(item: { id: string; title: string; description?: string; owner_user_id: string; owner_username?: string; gmt_subscribed?: string | null }): CollectionView {
  return {
    id: item.id,
    title: item.title,
    description: item.description,
    status: 'ACTIVE',
    created: undefined,
    updated: item.gmt_subscribed || undefined,
    owner_user_id: item.owner_user_id,
    owner_username: item.owner_username,
    is_published: true,
    published_at: item.gmt_subscribed || undefined,
  };
}

export default function CollectionsPage() {
  const [collections, setCollections] = useState<CollectionView[]>([]);
  const [subscribedCollections, setSubscribedCollections] = useState<CollectionView[]>([]);
  const [loading, setLoading] = useState(true);
  const [subscribedLoading, setSubscribedLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const loadCollections = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage('');
      const data = await collectionsApi.list();
      setCollections(data.items || []);
    } catch (error) {
      console.error('Failed to load collections:', error);
      setErrorMessage('Failed to load collections. Please refresh and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSubscribedCollections = useCallback(async () => {
    try {
      setSubscribedLoading(true);
      const data = await marketplaceApi.listSubscribedCollections();
      setSubscribedCollections((data.items || []).map(mapSharedToCollectionView));
    } catch (error) {
      console.error('Failed to load subscribed collections:', error);
      setSubscribedCollections([]);
    } finally {
      setSubscribedLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCollections();
  }, [loadCollections]);

  useEffect(() => {
    loadSubscribedCollections();
  }, [loadSubscribedCollections]);

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  const filteredCollections = useMemo(() => {
    if (!searchQuery) return collections;
    const query = searchQuery.toLowerCase();
    return collections.filter((collection) => (
      collection.title?.toLowerCase().includes(query) ||
      collection.description?.toLowerCase().includes(query)
    ));
  }, [collections, searchQuery]);

  const filteredSubscribedCollections = useMemo(() => {
    if (!searchQuery) return subscribedCollections;
    const query = searchQuery.toLowerCase();
    return subscribedCollections.filter((collection) => (
      collection.title?.toLowerCase().includes(query) ||
      collection.description?.toLowerCase().includes(query) ||
      collection.owner_username?.toLowerCase().includes(query)
    ));
  }, [subscribedCollections, searchQuery]);

  const handleCollectionCreated = useCallback(() => {
    loadCollections();
  }, [loadCollections]);

  const handleCollectionDeleted = useCallback(() => {
    loadCollections();
  }, [loadCollections]);

  const isEmpty = !loading && !subscribedLoading && filteredCollections.length === 0 && filteredSubscribedCollections.length === 0;

  return (
    <div className="collections-page">
      <div className="page-header">
        <div className="page-header-content">
          <h1 className="page-title">Collections</h1>
          <p className="page-description">
            By importing and systematically organizing your data sources into a structured dataset,
            you can significantly improve the contextual understanding and response accuracy of
            large language models (LLMs)
          </p>
        </div>
      </div>

      <div className="page-content">
        <div className="page-controls">
          <div className="search-wrapper">
            <SearchBar onSearch={handleSearch} />
          </div>
          <AddCollectionButton onCollectionCreated={handleCollectionCreated} />
        </div>

        {loading ? (
          <LoadingSkeleton count={6} />
        ) : errorMessage ? (
          <div className="error-state">{errorMessage}</div>
        ) : isEmpty ? (
          <div className="empty-state">
            {searchQuery ? 'No collections found matching your search.' : 'No collections yet. Create your first collection or browse the Marketplace to subscribe!'}
          </div>
        ) : (
          <div className="collections-grid">
            {filteredCollections.map((collection) => (
              <CollectionCard
                key={collection.id}
                collection={collection}
                onDeleted={handleCollectionDeleted}
              />
            ))}
            {filteredSubscribedCollections.map((collection) => (
              <CollectionCard
                key={`subscribed-${collection.id}`}
                collection={collection}
                fromMarketplace
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
