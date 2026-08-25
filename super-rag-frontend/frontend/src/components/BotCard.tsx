import { useMemo } from 'react';
import { MoreVertical } from 'lucide-react';
import type { BotView } from '../types';
import { formatDistanceToNow } from 'date-fns';
import './BotCard.css';

interface BotCardProps {
  bot: BotView;
  onDeleted?: () => void;
}

export default function BotCard({ bot, onDeleted }: BotCardProps) {
  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Unknown';
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true });
    } catch {
      return 'Unknown';
    }
  };

  const isPublic = Boolean(bot.is_published);
  const status = bot.status ?? 'ACTIVE';
  const statusLabel = status === 'INACTIVE' ? 'Inactive' : status === 'DELETED' ? 'Deleted' : 'Active';
  const statusClass = status === 'INACTIVE' ? 'inactive' : status === 'DELETED' ? 'deleted' : 'active';
  const updatedText = formatDate(bot.updated || bot.created);
  const avatarLabel = useMemo(() => {
    const trimmed = bot.title?.trim();
    return trimmed ? trimmed.charAt(0).toUpperCase() : 'B';
  }, [bot.title]);

  const handleCardClick = (e: React.MouseEvent) => {
    // 如果点击的是按钮或链接，不触发导航
    const target = e.target as HTMLElement;
    if (target.closest('button') || target.closest('a')) {
      return;
    }
    // TODO: 导航到 bot 详情页
    // if (bot.id) {
    //   navigate(`/bots/${bot.id}`);
    // }
  };

  return (
    <div className="bot-card" onClick={handleCardClick}>
      <div className="card-header">
        <div className="card-identity">
          <div className="card-icon">
            <span>{avatarLabel}</span>
          </div>
          <div className="card-title-section">
            <div className="card-title-row">
              <h3 className="card-title">{bot.title || 'Untitled'}</h3>
              <span className={`privacy-badge ${isPublic ? 'public' : 'private'}`}>
                {isPublic ? 'Public' : 'Private'}
              </span>
            </div>
            <span className="card-updated-top">{updatedText}</span>
          </div>
        </div>
        <div className="card-actions">
          <button className="card-action-btn" title="More options">
            <MoreVertical size={16} />
          </button>
        </div>
      </div>

      <p className="card-description">
        {bot.description || 'No description provided.'}
      </p>

      <div className="card-footer">
        <div className="card-meta">
          <span className={`card-status ${statusClass}`}>{statusLabel}</span>
          <span className="card-updated">Updated {updatedText}</span>
        </div>
      </div>
    </div>
  );
}
