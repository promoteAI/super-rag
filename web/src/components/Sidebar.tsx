import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Store,
  FolderOpen,
  MessageSquare,
  Plus,
  History,
  Settings,
  LogOut,
  Server,
  Trash2,
} from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import { botsApi, chatsApi, authApi } from '../api/client';
import type { Chat } from '../types';
import './Sidebar.css';

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [chatsExpanded, setChatsExpanded] = useState(true);
  const [chats, setChats] = useState<Chat[]>([]);
  const [loadingChats, setLoadingChats] = useState(false);
  const [creatingChat, setCreatingChat] = useState(false);
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null);
  
  // 用户信息
  const [userInfo, setUserInfo] = useState({
    username: '',
    email: '',
  });

  // 从 localStorage 读取用户信息
  useEffect(() => {
    const username = localStorage.getItem('user_username') || '';
    const email = localStorage.getItem('user_email') || '';
    setUserInfo({ username, email });
  }, []);

  const isActive = (path: string) => location.pathname === path;

  const loadChats = useCallback(async () => {
    try {
      setLoadingChats(true);
      // 先获取 bots 列表
      const botsData = await botsApi.list();
      const bots = botsData.items || [];
      
      // 如果有 bots，使用第一个 bot 来获取 chats
      if (bots.length > 0 && bots[0].id) {
        const chatsData = await chatsApi.list(bots[0].id);
        setChats(chatsData.items || []);
      } else {
        setChats([]);
      }
    } catch (error) {
      console.error('Failed to load chats:', error);
      setChats([]);
    } finally {
      setLoadingChats(false);
    }
  }, []);

  const handleCreateChat = useCallback(async () => {
    try {
      setCreatingChat(true);
      // 先获取 bots 列表
      const botsData = await botsApi.list();
      const bots = botsData.items || [];
      
      if (bots.length === 0 || !bots[0].id) {
        alert('No bots available. Please create a bot first.');
        return;
      }

      const botId = bots[0].id;
      // 创建新聊天
      const newChat = await chatsApi.create(botId);
      
      if (newChat.id) {
        // 导航到新创建的聊天页面
        navigate(`/chats/${newChat.id}`);
        // 刷新聊天列表
        await loadChats();
      } else {
        alert('Failed to create chat. Please try again.');
      }
    } catch (error) {
      console.error('Failed to create chat:', error);
      alert('Failed to create chat. Please try again.');
    } finally {
      setCreatingChat(false);
    }
  }, [navigate, loadChats]);

  const handleLogout = useCallback(async () => {
    try {
      await authApi.logout();
      // 登出成功，跳转到登录页面
      navigate('/login');
    } catch (error) {
      console.error('Logout error:', error);
      // 即使登出接口失败，也清除本地存储并跳转
      navigate('/login');
    }
  }, [navigate]);

  const handleDeleteChat = useCallback(async (chatId: string, event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    
    if (deletingChatId || !chatId) {
      return;
    }

    const chat = chats.find(c => c.id === chatId);
    const chatTitle = chat?.title || `Chat ${chatId}`;
    
    const confirmed = window.confirm(
      `确定要删除 "${chatTitle}" 吗？此操作无法撤销。`
    );
    
    if (!confirmed) {
      return;
    }

    try {
      setDeletingChatId(chatId);
      
      // 获取 botId
      const botsData = await botsApi.list();
      const bots = botsData.items || [];
      
      if (bots.length === 0 || !bots[0].id) {
        throw new Error('No bot available');
      }

      const botId = bots[0].id;
      await chatsApi.delete(botId, chatId);
      
      // 如果删除的是当前正在查看的聊天，导航到新聊天页面
      if (location.pathname === `/chats/${chatId}`) {
        navigate('/chats/new');
      }
      
      // 刷新聊天列表
      await loadChats();
    } catch (error) {
      console.error('Failed to delete chat:', error);
      alert('删除失败，请重试。');
    } finally {
      setDeletingChatId(null);
    }
  }, [chats, deletingChatId, navigate, location.pathname, loadChats]);

  useEffect(() => {
    loadChats();
  }, [loadChats]);

  useEffect(() => {
    const handleChatTitleUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ chatId?: string; title?: string }>).detail;
      if (!detail?.chatId || !detail?.title) return;
      setChats((prev) =>
        prev.map((chat) =>
          chat.id === detail.chatId ? { ...chat, title: detail.title } : chat
        )
      );
    };

    window.addEventListener('chat-title-updated', handleChatTitleUpdated as EventListener);
    return () =>
      window.removeEventListener('chat-title-updated', handleChatTitleUpdated as EventListener);
  }, []);

  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        <Link
          to="/marketplace"
          className={`nav-item ${isActive('/marketplace') ? 'active' : ''}`}
          title="Marketplace"
        >
          <Store size={20} />
        </Link>
        
        <Link
          to="/collections"
          className={`nav-item ${isActive('/collections') ? 'active' : ''}`}
          title="Collections"
        >
          <FolderOpen size={20} />
        </Link>

        <Link
          to="/model-providers"
          className={`nav-item ${isActive('/model-providers') ? 'active' : ''}`}
          title="Model Providers"
        >
          <Server size={20} />
        </Link>
        
        <Link
          to="/chats/new"
          className={`nav-item ${isActive('/chats') ? 'active' : ''}`}
          title="Chats"
        >
          <MessageSquare size={20} />
        </Link>
        
        <Link
          to="/settings"
          className={`nav-item ${isActive('/settings') ? 'active' : ''}`}
          title="Settings"
        >
          <Settings size={20} />
        </Link>
      </nav>

      <div className="sidebar-user">
        <div className="user-avatar">
          <span>
            {userInfo.username
              ? userInfo.username.charAt(0).toUpperCase()
              : userInfo.email
              ? userInfo.email.charAt(0).toUpperCase()
              : 'U'}
          </span>
        </div>
        <div className="user-info">
          <div className="user-name">{userInfo.username || '用户'}</div>
          <div className="user-email">{userInfo.email || ''}</div>
        </div>
        <button className="user-logout" onClick={handleLogout} title="Log out">
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
}
