import './Header.css';

export default function Header() {
  return (
    <header className="header">
      <div className="header-main">
        <div className="header-left">
          <div className="logo">
            <div className="logo-icon">
              <svg
                width="50"
                height="50"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                {/* 外层神经网络/能量环 */}
                <circle
                  cx="12"
                  cy="12"
                  r="8"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {/* 节点 */}
                <circle cx="7.5" cy="10" r="1.3" fill="currentColor" />
                <circle cx="16.5" cy="10" r="1.3" fill="currentColor" />
                <circle cx="12" cy="16" r="1.3" fill="currentColor" />
                {/* 连接边，象征智能体路由/决策 */}
                <path
                  d="M7.5 10L12 16L16.5 10"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {/* 顶部输入火花，象征 AI 感知/指令入口 */}
                <path
                  d="M12 5L12 7.4"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
                <circle cx="12" cy="4.2" r="0.9" fill="currentColor" />
              </svg>
            </div>
            <span className="logo-text">SuperRAG</span>
          </div>
        </div>
      </div>
    </header>
  );
}
