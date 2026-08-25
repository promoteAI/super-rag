import { useState, useMemo, useEffect } from 'react';
import { Search, Package } from 'lucide-react';
import { nodeflowApi, type NodeflowNodeType, type NodeflowRegistryPackage } from '../api/client';
import './NodeManagerPage.css';

type PackageStatus = 'installed' | 'available' | 'update';

interface NodePackage {
  id: string;
  name: string;
  identifier: string;
  description: string;
  version?: string;
  latestVersion?: string;
  status: PackageStatus;
  node_types?: string[];
  install?: string;
  builtin?: boolean;
}

interface NodeResult {
  id: string;
  name: string;
  type: string;
  category: string;
  description?: string;
}

type TabType = 'all' | 'installed' | 'available' | 'updates';

function buildPackagesFromApi(
  packs: NodeflowRegistryPackage[],
  installedTypeSet: Set<string>
): NodePackage[] {
  return packs.map((p, i) => {
    const id = p.repo_id.replace(/\//g, '-') || `pack-${i}`;
    const nodeTypes = p.node_types || [];
    const isInstalled =
      p.builtin === true || nodeTypes.some((t) => installedTypeSet.has(t));
    return {
      id,
      name: p.name,
      identifier: p.repo_id,
      description: p.description || '',
      version: p.builtin ? '内置' : undefined,
      status: isInstalled ? 'installed' : 'available',
      node_types: nodeTypes,
      install: p.install,
      builtin: p.builtin,
    };
  });
}

export default function NodeManagerPage() {
  const [activeTab, setActiveTab] = useState<TabType>('all');
  const [packageSearch, setPackageSearch] = useState('');
  const [nodeSearch, setNodeSearch] = useState('');
  const [packages, setPackages] = useState<NodePackage[]>([]);
  const [nodeTypes, setNodeTypes] = useState<NodeflowNodeType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([nodeflowApi.listPacks(), nodeflowApi.listNodeTypes()])
      .then(([packsRes, typesRes]) => {
        if (cancelled) return;
        const installedTypeSet = new Set(typesRes.node_types.map((t) => t.type));
        setNodeTypes(typesRes.node_types);
        setPackages(buildPackagesFromApi(packsRes.packages, installedTypeSet));
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || '加载节点包列表失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredPackages = useMemo(() => {
    let filtered = packages;

    if (activeTab === 'installed') {
      filtered = filtered.filter((pkg) => pkg.status === 'installed');
    } else if (activeTab === 'available') {
      filtered = filtered.filter((pkg) => pkg.status === 'available');
    } else if (activeTab === 'updates') {
      filtered = filtered.filter((pkg) => pkg.status === 'update');
    }

    if (packageSearch) {
      const query = packageSearch.toLowerCase();
      filtered = filtered.filter(
        (pkg) =>
          pkg.name.toLowerCase().includes(query) ||
          pkg.identifier.toLowerCase().includes(query) ||
          (pkg.description && pkg.description.toLowerCase().includes(query))
      );
    }

    if (nodeSearch) {
      const query = nodeSearch.toLowerCase();
      filtered = filtered.filter(
        (pkg) =>
          pkg.name.toLowerCase().includes(query) ||
          pkg.identifier.toLowerCase().includes(query) ||
          (pkg.node_types && pkg.node_types.some((t) => t.toLowerCase().includes(query)))
      );
    }

    return filtered;
  }, [activeTab, packageSearch, nodeSearch, packages]);

  const filteredNodeResults = useMemo(() => {
    if (!nodeSearch) return [] as NodeResult[];
    const query = nodeSearch.toLowerCase();
    return nodeTypes
      .filter(
        (t) =>
          t.type.toLowerCase().includes(query) ||
          t.label.toLowerCase().includes(query) ||
          (t.category && t.category.toLowerCase().includes(query)) ||
          (t.description && t.description.toLowerCase().includes(query))
      )
      .map((t) => ({
        id: t.type,
        name: t.label,
        type: t.type,
        category: t.category,
        description: t.description,
      }));
  }, [nodeSearch, nodeTypes]);

  const handleInstall = (pkg: NodePackage) => {
    if (pkg.install) {
      navigator.clipboard.writeText(pkg.install);
      // 可在此加 toast：已复制安装命令，请在服务器环境中执行后重启服务
    }
    // 实际安装需在部署环境中执行 pip/uv，此处仅展示或复制安装命令
  };

  const handleUninstall = (pkg: NodePackage) => {
    if (pkg.builtin) return;
    console.log('Uninstall 需在服务器执行 pip uninstall，对应包名请查看 repo_id:', pkg.identifier);
  };

  if (loading) {
    return (
      <div className="node-manager-page">
        <div className="node-manager-loading">加载节点包列表中…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="node-manager-page">
        <div className="node-manager-error">{error}</div>
      </div>
    );
  }

  return (
    <div className="node-manager-page">
      <div className="node-manager-controls">
        <div className="node-manager-tabs">
          <button
            className={`node-manager-tab ${activeTab === 'all' ? 'active' : ''}`}
            onClick={() => setActiveTab('all')}
          >
            All Packages
          </button>
          <button
            className={`node-manager-tab ${activeTab === 'installed' ? 'active' : ''}`}
            onClick={() => setActiveTab('installed')}
          >
            Installed
          </button>
          <button
            className={`node-manager-tab ${activeTab === 'available' ? 'active' : ''}`}
            onClick={() => setActiveTab('available')}
          >
            Available
          </button>
          <button
            className={`node-manager-tab ${activeTab === 'updates' ? 'active' : ''}`}
            onClick={() => setActiveTab('updates')}
          >
            Updates
          </button>
        </div>

        <div className="node-manager-search">
          <div className="search-input-wrapper">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              className="search-input"
              placeholder="Search packages..."
              value={packageSearch}
              onChange={(e) => setPackageSearch(e.target.value)}
            />
          </div>
          <div className="search-input-wrapper">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              className="search-input"
              placeholder="Search specific nodes..."
              value={nodeSearch}
              onChange={(e) => setNodeSearch(e.target.value)}
            />
          </div>
        </div>
      </div>

      {nodeSearch && (
        <div className="node-results-section">
          <div className="node-results-header">
            <span className="node-results-title">NODE RESULTS</span>
            <span className="node-results-count">
              {filteredNodeResults.length > 0
                ? `(${filteredNodeResults.length})`
                : '(0)'}
            </span>
          </div>
          <div className="node-results-list">
            {filteredNodeResults.map((node) => (
              <div key={node.id} className="node-result-card">
                <div className="node-result-main">
                  <h3 className="node-result-title">{node.name}</h3>
                  <p className="node-result-description">{node.description || node.type}</p>
                  <div className="node-result-meta">
                    <span className="node-result-identifier">{node.type}</span>
                    {node.category && (
                      <span className="node-result-category">{node.category}</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="node-manager-grid">
        {filteredPackages.map((pkg) => (
          <div key={pkg.id} className="node-package-card">
            <div className="package-card-header">
              <div className="package-icon">
                <Package size={20} />
              </div>
              <div className="package-title-section">
                <h3 className="package-title">{pkg.name}</h3>
                <p className="package-identifier">{pkg.identifier}</p>
              </div>
            </div>
            <p className="package-description">{pkg.description}</p>
            {pkg.node_types && pkg.node_types.length > 0 && (
              <p className="package-node-types">
                节点：{pkg.node_types.join(', ')}
              </p>
            )}
            <div className="package-footer">
              <div className="package-version">
                {pkg.status === 'installed' && (
                  <>
                    <span className="version-label">{pkg.builtin ? '内置' : 'Ver:'}</span>
                    <span className="version-value">{pkg.version || '—'}</span>
                  </>
                )}
                {pkg.status === 'available' && pkg.install && (
                  <span className="version-hint">安装后重启服务生效</span>
                )}
              </div>
              <div className="package-actions">
                {pkg.status === 'installed' && (
                  <>
                    <span className="package-status-badge installed">已安装</span>
                    {!pkg.builtin && (
                      <button
                        className="package-action-btn uninstall"
                        onClick={() => handleUninstall(pkg)}
                      >
                        卸载
                      </button>
                    )}
                  </>
                )}
                {pkg.status === 'available' && (
                  <button
                    className="package-action-btn install"
                    onClick={() => handleInstall(pkg)}
                    title={pkg.install || 'Copy install command'}
                  >
                    {pkg.install ? '复制安装命令' : '安装'}
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {filteredPackages.length === 0 && filteredNodeResults.length === 0 && (
        <div className="node-manager-empty">
          <p>No packages found matching your search criteria.</p>
        </div>
      )}
    </div>
  );
}
