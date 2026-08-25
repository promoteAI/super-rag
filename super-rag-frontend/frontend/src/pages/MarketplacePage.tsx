import { useState, useEffect, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen } from 'lucide-react';
import { marketplaceApi } from '../api/client';
import type { CollectionView } from '../types';
import CollectionCard from '../components/CollectionCard';
import SearchBar from '../components/SearchBar';
import LoadingSkeleton from '../components/LoadingSkeleton';
import './MarketplacePage.css';

export default function MarketplacePage() {
  const [collections, setCollections] = useState<CollectionView[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const loadCollections = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage('');
      const data = await marketplaceApi.listCollections();
      const mapped: CollectionView[] = (data.items || []).map((item) => ({
        id: item.id,
        title: item.title,
        description: item.description,
        status: 'ACTIVE',
        // 对于市场卡片，没有集合本身的更新时间，用订阅时间或发布日期；可能为空
        created: undefined,
        updated: item.gmt_subscribed || undefined,
        owner_user_id: item.owner_user_id,
        owner_username: item.owner_username,
        is_published: true,
        published_at: item.gmt_subscribed || undefined,
      }));
      setCollections(mapped);
    } catch (error) {
      console.error('Failed to load marketplace collections:', error);
      setErrorMessage('Failed to load marketplace collections. Please refresh and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCollections();
  }, [loadCollections]);

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

  return (
    <div className="marketplace-page">
      <div className="page-header marketplace-page-header">
        <div className="page-header-content">
          <h1 className="page-title">Marketplace</h1>
          <p className="page-description">
            Discover and subscribe to quality knowledge collections shared by community,
            expand your knowledge boundaries.
          </p>
        </div>
        <Link to="/collections" className="marketplace-collections-btn">
          <BookOpen size={18} />
          Collections
        </Link>
      </div>

      <div className="page-content">
        <div className="page-controls">
          <div className="search-wrapper">
            <SearchBar onSearch={handleSearch} />
          </div>
        </div>

        {loading ? (
          <LoadingSkeleton count={6} />
        ) : errorMessage ? (
          <div className="error-state">{errorMessage}</div>
        ) : filteredCollections.length === 0 ? (
          <div className="empty-state">
            {searchQuery
              ? 'No public collections found matching your search.'
              : 'No public collections available yet.'}
          </div>
        ) : (
          <div className="collections-grid">
            {filteredCollections.map((collection) => (
              <CollectionCard
                key={collection.id}
                collection={collection}
                fromMarketplace
                marketplaceList
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

