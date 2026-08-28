import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Store, FolderOpen, MessageSquare, Settings, LogOut, Server, PanelLeftClose, PanelLeftOpen, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import { authApi, botsApi, chatsApi } from '../api/client';
import type { Chat } from '../types';
import './Sidebar.css';

const COLLAPSE_KEY = 'sidebar_collapsed';
const RECENTS_EXPANDED_KEY = 'recents_expanded';

function groupChatsByDate(chats: Chat[]): Record<string, Chat[]> {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
  const groups: Record<string, Chat[]> = { TODAY: [], YESTERDAY: [], OTHER: [] };
  for (const chat of chats) {
    const d = chat.updated ? new Date(chat.updated) : new Date(chat.created || 0);
    if (d >= today) groups.TODAY.push(chat);
    else if (d >= yesterday) groups.YESTERDAY.push(chat);
    else groups.OTHER.push(chat);
  }
  return groups;
}

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [userInfo, setUserInfo] = useState({ username: '', email: '' });
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === '1'; } catch { return false; }
  });
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [chats, setChats] = useState<Chat[]>([]);
  const [chatsLoading, setChatsLoading] = useState(false);
  const [hoveredChatId, setHoveredChatId] = useState<string | null>(null);
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null);
  const [recentsExpanded, setRecentsExpanded] = useState<boolean>(() => {
    try { return localStorage.getItem(RECENTS_EXPANDED_KEY) !== '0'; } catch { return true; }
  });

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

  const loadChats = useCallback(async () => {
    if (collapsed) { setChats([]); return; }
    try {
      setChatsLoading(true);
      const botsData = await botsApi.list();
      const bots = botsData.items || [];
      if (bots.length === 0 || !bots[0].id) { setChats([]); return; }
      const chatsData = await chatsApi.list(bots[0].id);
      setChats(chatsData.items || []);
    } catch { setChats([]); }
    finally { setChatsLoading(false); }
  }, [collapsed]);

  useEffect(() => { loadChats(); }, [loadChats]);

  const isActive = (path: string) => location.pathname === path;
  const isChatPage = location.pathname.startsWith('/chats');

  const toggleCollapsed = useCallback(() => {
    setCollapsed(prev => { const next = !prev; try { localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0'); } catch {} return next; });
  }, []);

  const handleLogout = useCallback(async () => {
    try { await authApi.logout(); navigate('/login'); } catch { navigate('/login'); }
  }, [navigate]);

  const handleCreateChat = useCallback(async () => {
    try {
      const botsData = await botsApi.list();
      const bots = botsData.items || [];
      if (bots.length === 0 || !bots[0].id) { navigate('/chats/new'); return; }
      const newChat = await chatsApi.create(bots[0].id);
      if (newChat.id) navigate('/chats/' + newChat.id); else navigate('/chats/new');
    } catch { navigate('/chats/new'); }
  }, [navigate]);

  const toggleRecents = useCallback(() => {
    setRecentsExpanded(prev => {
      const next = !prev;
      try { localStorage.setItem(RECENTS_EXPANDED_KEY, next ? '1' : '0'); } catch {}
      return next;
    });
  }, []);

  const handleDeleteChat = useCallback(async (chatId: string, e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    if (deletingChatId || !chatId) return;
    try {
      setDeletingChatId(chatId);
      const botsData = await botsApi.list();
      const bots = botsData.items || [];
      if (bots[0]?.id) await chatsApi.delete(bots[0].id, chatId);
      if (location.pathname === '/chats/' + chatId) navigate('/chats/new');
      await loadChats();
    } catch {} finally { setDeletingChatId(null); }
  }, [deletingChatId, location.pathname, navigate, loadChats]);

  const initial = userInfo.username ? userInfo.username[0].toUpperCase() : 'U';
  const grouped = groupChatsByDate(chats);

  return (
    <aside className={'sidebar ' + (collapsed ? 'sidebar-collapsed' : 'sidebar-expanded')}>
      <nav className='sidebar-nav'>
        <div className='sidebar-brand-row'>
          <div className='sidebar-brand'>
            <div className='sidebar-brand-icon'><Store size={14} /></div>
            <span className='sidebar-brand-text'>SuperRAG</span>
          </div>
          <button className='sidebar-toggle' onClick={toggleCollapsed} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            {collapsed ? <PanelLeftOpen size={14} /> : <PanelLeftClose size={14} />}
          </button>
        </div>

        <Link to='/marketplace' className={'nav-item ' + (isActive('/marketplace') ? 'active' : '')}>
          <Store size={16} /><span className='nav-label'>Marketplace</span>
        </Link>
        <Link to='/collections' className={'nav-item ' + (isActive('/collections') ? 'active' : '')}>
          <FolderOpen size={16} /><span className='nav-label'>Knowledge Base</span>
        </Link>
        <Link to='/model-providers' className={'nav-item ' + (isActive('/model-providers') ? 'active' : '')}>
          <Server size={16} /><span className='nav-label'>Model Providers</span>
        </Link>
        <Link to='/chats' className={'nav-item ' + (isChatPage ? 'active' : '')}>
          <MessageSquare size={16} /><span className='nav-label'>Chats</span>
        </Link>

        {!collapsed && isChatPage && (
          <div className='recents-section'>
            <div className='recents-header'>
              <span className='recents-title'>Recents</span>
              <button
                className='recents-new-btn'
                onClick={toggleRecents}
                title={recentsExpanded ? 'Collapse chat history' : 'Expand chat history'}
                aria-label={recentsExpanded ? 'Collapse chat history' : 'Expand chat history'}
              >
                {recentsExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            </div>
            {recentsExpanded && chatsLoading ? (
              <div className='recents-loading'>Loading...</div>
            ) : recentsExpanded && chats.length === 0 ? (
              <div className='recents-empty'>No recent chats</div>
            ) : recentsExpanded ? (
              <>
                {['TODAY', 'YESTERDAY', 'OTHER'].map(groupKey => {
                  const groupChats = grouped[groupKey];
                  if (!groupChats || groupChats.length === 0) return null;
                  return (
                    <div key={groupKey} className='recents-group'>
                      <div className='recents-group-header'>{groupKey === 'TODAY' ? 'Today' : groupKey === 'YESTERDAY' ? 'Yesterday' : 'Previous'}</div>
                      {groupChats.map(chat => (
                        <div
                          key={chat.id}
                          className={'recents-item-wrapper' + (chat.id && location.pathname === '/chats/' + chat.id ? ' active' : '')}
                          onMouseEnter={() => setHoveredChatId(chat.id || null)}
                          onMouseLeave={() => setHoveredChatId(null)}
                        >
                          {chat.id ? (
                            <Link to={'/chats/' + chat.id} className='recents-item'>
                              <MessageSquare size={14} className='recents-item-icon' />
                              <span className='recents-item-title'>{chat.title || 'Untitled'}</span>
                            </Link>
                          ) : (
                            <button className='recents-item' onClick={handleCreateChat}>
                              <MessageSquare size={14} className='recents-item-icon' />
                              <span className='recents-item-title'>New Chat</span>
                            </button>
                          )}
                          {chat.id && hoveredChatId === chat.id && deletingChatId !== chat.id && (
                            <button className='recents-delete-btn' onClick={(e) => handleDeleteChat(chat.id!, e)} title='Delete'><Trash2 size={12} /></button>
                          )}
                        </div>
                      ))}
                    </div>
                  );
                })}
              </>
            ) : null}
          </div>
        )}

        <div className='sidebar-footer'>
          <div className='user-menu-container'>
            <button className='sidebar-user' onClick={(e) => { e.stopPropagation(); setShowUserMenu(!showUserMenu); }}>
              <div className='user-avatar'>{initial}</div>
              {!collapsed && (
                <div className='user-info'>
                  <div className='user-name'>{userInfo.username || 'User'}</div>
                  <div className='user-email'>{userInfo.email}</div>
                </div>
              )}
            </button>
            {showUserMenu && !collapsed && (
              <div className='user-dropdown' onClick={(e) => e.stopPropagation()}>
                <Link to='/settings' className='user-dropdown-item' onClick={() => setShowUserMenu(false)}>
                  <Settings size={14} />Settings
                </Link>
                <button className='user-dropdown-item user-dropdown-logout' onClick={handleLogout}>
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