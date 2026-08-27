import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Store, FolderOpen, MessageSquare, Settings, LogOut, Server, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import { authApi } from '../api/client';
import './Sidebar.css';

const COLLAPSE_KEY = 'sidebar_collapsed';

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [userInfo, setUserInfo] = useState({ username: '', email: '' });
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === '1'; } catch { return false; }
  });
  const [showUserMenu, setShowUserMenu] = useState(false);

  useEffect(() => {
    const username = localStorage.getItem('user_username') || '';
    const email = localStorage.getItem('user_email') || '';
    setUserInfo({ username, email });
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.user-menu-container')) setShowUserMenu(false);
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  const isActive = (path: string) => location.pathname === path;

  const toggleCollapsed = useCallback(() => {
    setCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0'); } catch {}
      return next;
    });
  }, []);

  const handleLogout = useCallback(async () => {
    try { await authApi.logout(); navigate('/login'); }
    catch { navigate('/login'); }
  }, [navigate]);

  const initial = userInfo.username ? userInfo.username[0].toUpperCase() : 'U';

  return (
    <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : 'sidebar-expanded'}`}>
      <nav className="sidebar-nav">
        <div className="sidebar-brand-row">
          <div className="sidebar-brand">
            <div className="sidebar-brand-icon"><Store size={14} /></div>
            <span className="sidebar-brand-text">SuperRAG</span>
          </div>
          <button className="sidebar-toggle" onClick={toggleCollapsed} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            {collapsed ? <PanelLeftOpen size={14} /> : <PanelLeftClose size={14} />}
          </button>
        </div>

        <Link to="/marketplace" className={`nav-item ${isActive('/marketplace') ? 'active' : ''}`}>
          <Store size={16} /><span className="nav-label">Marketplace</span>
        </Link>
        <Link to="/collections" className={`nav-item ${isActive('/collections') ? 'active' : ''}`}>
          <FolderOpen size={16} /><span className="nav-label">Knowledge Base</span>
        </Link>
        <Link to="/model-providers" className={`nav-item ${isActive('/model-providers') ? 'active' : ''}`}>
          <Server size={16} /><span className="nav-label">Model Providers</span>
        </Link>
        <Link to="/chats" className={`nav-item ${isActive('/chats') || isActive('/chats/new') ? 'active' : ''}`}>
          <MessageSquare size={16} /><span className="nav-label">Chats</span>
        </Link>

        <div className="sidebar-footer">
          <div className="user-menu-container">
            <button className="sidebar-user" onClick={(e) => { e.stopPropagation(); setShowUserMenu(!showUserMenu); }}>
              <div className="user-avatar">{initial}</div>
              {!collapsed && (
                <div className="user-info">
                  <div className="user-name">{userInfo.username || 'User'}</div>
                  <div className="user-email">{userInfo.email}</div>
                </div>
              )}
            </button>
            {showUserMenu && !collapsed && (
              <div className="user-dropdown" onClick={(e) => e.stopPropagation()}>
                <Link to="/settings" className="user-dropdown-item" onClick={() => setShowUserMenu(false)}>
                  <Settings size={14} />Settings
                </Link>
                <button className="user-dropdown-item user-dropdown-logout" onClick={handleLogout}>
                  <LogOut size={14} />Log Out
                </button>
              </div>
            )}
          </div>
        </div>
      </nav>
    </aside>
  );
}