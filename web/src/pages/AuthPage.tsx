import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import './AuthPage.css';
import { authApi } from '../api/client';

type AuthMode = 'login' | 'register';

export default function AuthPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const isRegisterRoute = useMemo(
    () => location.pathname === '/register',
    [location.pathname]
  );
  const [mode, setMode] = useState<AuthMode>(
    isRegisterRoute ? 'register' : 'login'
  );

  // 表单状态
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    agreeTerms: false,
    rememberMe: false,
  });

  // 加载和错误状态
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 修改密码模态框状态
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [changePasswordData, setChangePasswordData] = useState({
    oldPassword: '',
    newPassword: '',
    confirmNewPassword: '',
  });
  const [changePasswordError, setChangePasswordError] = useState<string | null>(null);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  useEffect(() => {
    setMode(isRegisterRoute ? 'register' : 'login');
    // 切换模式时重置表单和错误
    setFormData({
      username: '',
      email: '',
      password: '',
      confirmPassword: '',
      agreeTerms: false,
      rememberMe: false,
    });
    setError(null);
  }, [isRegisterRoute]);

  const handleInputChange = (field: string, value: string | boolean) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // 清除错误信息
    if (error) {
      setError(null);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (mode === 'register') {
      // 验证表单
      if (!formData.username.trim()) {
        setError('请输入用户名');
        return;
      }
      if (!formData.email.trim()) {
        setError('请输入邮箱');
        return;
      }
      if (!formData.password) {
        setError('请输入密码');
        return;
      }
      if (formData.password.length < 8) {
        setError('密码长度至少为8位');
        return;
      }
      if (formData.password !== formData.confirmPassword) {
        setError('两次输入的密码不一致');
        return;
      }
      if (!formData.agreeTerms) {
        setError('请同意服务条款');
        return;
      }

      // 调用注册接口
      setIsLoading(true);
      try {
        await authApi.register({
          username: formData.username.trim(),
          email: formData.email.trim(),
          password: formData.password,
        });
        // 注册成功，保存用户信息到 localStorage
        localStorage.setItem('user_username', formData.username.trim());
        localStorage.setItem('user_email', formData.email.trim());
        // 跳转到首页
        navigate('/');
      } catch (err: any) {
        setError(err.message || '注册失败，请稍后重试');
      } finally {
        setIsLoading(false);
      }
    } else {
      // 登录逻辑
      // 验证表单
      if (!formData.username.trim()) {
        setError('请输入用户名');
        return;
      }
      if (!formData.password) {
        setError('请输入密码');
        return;
      }

      // 调用登录接口
      setIsLoading(true);
      try {
        await authApi.login({
          username: formData.username.trim(),
          password: formData.password,
        });
        // 登录成功，跳转到首页
        navigate('/');
      } catch (err: any) {
        setError(err.message || '登录失败，请检查用户名和密码');
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleChangePassword = async () => {
    setChangePasswordError(null);

    // 验证表单
    if (!changePasswordData.oldPassword) {
      setChangePasswordError('请输入当前密码');
      return;
    }
    if (!changePasswordData.newPassword) {
      setChangePasswordError('请输入新密码');
      return;
    }
    if (changePasswordData.newPassword.length < 8) {
      setChangePasswordError('新密码长度至少为8位');
      return;
    }
    if (changePasswordData.newPassword !== changePasswordData.confirmNewPassword) {
      setChangePasswordError('两次输入的新密码不一致');
      return;
    }
    if (changePasswordData.oldPassword === changePasswordData.newPassword) {
      setChangePasswordError('新密码不能与当前密码相同');
      return;
    }

    // 调用修改密码接口
    setIsChangingPassword(true);
    try {
      await authApi.changePassword({
        old_password: changePasswordData.oldPassword,
        new_password: changePasswordData.newPassword,
      });
      // 修改成功，关闭模态框并重置表单
      setShowChangePassword(false);
      setChangePasswordData({
        oldPassword: '',
        newPassword: '',
        confirmNewPassword: '',
      });
      setChangePasswordError(null);
      // 显示成功消息
      alert('密码修改成功！');
    } catch (err: any) {
      setChangePasswordError(err.message || '修改密码失败，请检查当前密码是否正确');
    } finally {
      setIsChangingPassword(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <section className="auth-left">
          <div className="auth-brand">
            <span className="auth-badge">欢迎使用 Super RAG</span>
            <h1>让企业知识触手可及</h1>
            <p>
              统一接入、智能检索、可信回答，帮助团队把文档变成可对话的知识资产。
            </p>
          </div>
          <ul className="auth-points">
            <li>
              <span className="auth-point-icon">✔</span>
              <div>
                <strong>知识集中管理</strong>
                <span>连接多源资料，统一沉淀与更新</span>
              </div>
            </li>
            <li>
              <span className="auth-point-icon">⚡</span>
              <div>
                <strong>智能检索增强</strong>
                <span>语义召回与重排，答案更精准</span>
              </div>
            </li>
            <li>
              <span className="auth-point-icon">🤝</span>
              <div>
                <strong>团队协同可控</strong>
                <span>权限可配、流程可审、知识可追踪</span>
              </div>
            </li>
          </ul>
          <div className="auth-illustration">
            <div className="auth-illustration-glow" />
            <div className="auth-illustration-panel">
              <div className="auth-illustration-line" />
              <div className="auth-illustration-line short" />
            </div>
          </div>
        </section>

        <section className="auth-right">
          <div className="auth-tabs">
            <button
              type="button"
              className={mode === 'login' ? 'active' : ''}
              onClick={() => setMode('login')}
            >
              登录
            </button>
            <button
              type="button"
              className={mode === 'register' ? 'active' : ''}
              onClick={() => setMode('register')}
            >
              注册
            </button>
          </div>

          <h2>{mode === 'login' ? '欢迎回来' : '创建账号'}</h2>
          <p className="auth-subtitle">
            {mode === 'login'
              ? '请登录你的账号继续使用'
              : '注册后即可开启高效知识体验'}
          </p>

          <form className="auth-form" onSubmit={handleSubmit}>
            {error && (
              <div style={{ 
                padding: '0.75rem', 
                borderRadius: '8px', 
                background: '#fee2e2', 
                color: '#dc2626', 
                fontSize: '0.9rem',
                marginBottom: '0.5rem'
              }}>
                {error}
              </div>
            )}

            <label className="auth-field">
              <span>用户名</span>
              <input 
                type="text" 
                placeholder="请输入用户名" 
                required 
                value={formData.username}
                onChange={(e) => handleInputChange('username', e.target.value)}
                disabled={isLoading}
              />
            </label>
            {mode === 'register' && (
              <label className="auth-field">
                <span>邮箱</span>
                <input 
                  type="email" 
                  placeholder="请输入邮箱" 
                  required 
                  value={formData.email}
                  onChange={(e) => handleInputChange('email', e.target.value)}
                  disabled={isLoading}
                />
              </label>
            )}
            <label className="auth-field">
              <span>密码</span>
              <input 
                type="password" 
                placeholder="请输入密码" 
                required 
                value={formData.password}
                onChange={(e) => handleInputChange('password', e.target.value)}
                disabled={isLoading}
              />
            </label>
            {mode === 'register' && (
              <label className="auth-field">
                <span>确认密码</span>
                <input 
                  type="password" 
                  placeholder="再次输入密码" 
                  required 
                  value={formData.confirmPassword}
                  onChange={(e) => handleInputChange('confirmPassword', e.target.value)}
                  disabled={isLoading}
                />
              </label>
            )}

            <div className="auth-meta">
              {mode === 'login' ? (
                <>
                  <label className="auth-checkbox">
                    <input 
                      type="checkbox" 
                      checked={formData.rememberMe}
                      onChange={(e) => handleInputChange('rememberMe', e.target.checked)}
                      disabled={isLoading}
                    />
                    <span>记住我</span>
                  </label>
                  <button 
                    type="button" 
                    className="auth-link"
                    onClick={() => setShowChangePassword(true)}
                  >
                    忘记密码？
                  </button>
                </>
              ) : (
                <label className="auth-checkbox">
                  <input 
                    type="checkbox" 
                    required 
                    checked={formData.agreeTerms}
                    onChange={(e) => handleInputChange('agreeTerms', e.target.checked)}
                    disabled={isLoading}
                  />
                  <span>我已阅读并同意服务条款</span>
                </label>
              )}
            </div>

            <button 
              className="auth-submit" 
              type="submit"
              disabled={isLoading}
            >
              {isLoading ? '处理中...' : mode === 'login' ? '登录' : '注册并进入'}
            </button>
          </form>
        </section>
      </div>

      {/* 修改密码模态框 */}
      {showChangePassword && (
        <div 
          className="auth-modal-overlay"
          onClick={() => {
            if (!isChangingPassword) {
              setShowChangePassword(false);
              setChangePasswordData({
                oldPassword: '',
                newPassword: '',
                confirmNewPassword: '',
              });
              setChangePasswordError(null);
            }
          }}
        >
          <div 
            className="auth-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="auth-modal-header">
              <h2>修改密码</h2>
              <button
                type="button"
                className="auth-modal-close"
                onClick={() => {
                  setShowChangePassword(false);
                  setChangePasswordData({
                    oldPassword: '',
                    newPassword: '',
                    confirmNewPassword: '',
                  });
                  setChangePasswordError(null);
                }}
                disabled={isChangingPassword}
              >
                ×
              </button>
            </div>

            <div className="auth-modal-body">
              {changePasswordError && (
                <div style={{ 
                  padding: '0.75rem', 
                  borderRadius: '8px', 
                  background: '#fee2e2', 
                  color: '#dc2626', 
                  fontSize: '0.9rem',
                  marginBottom: '1rem'
                }}>
                  {changePasswordError}
                </div>
              )}

              <label className="auth-field">
                <span>当前密码</span>
                <input 
                  type="password" 
                  placeholder="请输入当前密码" 
                  required 
                  value={changePasswordData.oldPassword}
                  onChange={(e) => {
                    setChangePasswordData(prev => ({ ...prev, oldPassword: e.target.value }));
                    if (changePasswordError) setChangePasswordError(null);
                  }}
                  disabled={isChangingPassword}
                />
              </label>

              <label className="auth-field">
                <span>新密码</span>
                <input 
                  type="password" 
                  placeholder="请输入新密码（至少8位）" 
                  required 
                  value={changePasswordData.newPassword}
                  onChange={(e) => {
                    setChangePasswordData(prev => ({ ...prev, newPassword: e.target.value }));
                    if (changePasswordError) setChangePasswordError(null);
                  }}
                  disabled={isChangingPassword}
                />
              </label>

              <label className="auth-field">
                <span>确认新密码</span>
                <input 
                  type="password" 
                  placeholder="请再次输入新密码" 
                  required 
                  value={changePasswordData.confirmNewPassword}
                  onChange={(e) => {
                    setChangePasswordData(prev => ({ ...prev, confirmNewPassword: e.target.value }));
                    if (changePasswordError) setChangePasswordError(null);
                  }}
                  disabled={isChangingPassword}
                />
              </label>
            </div>

            <div className="auth-modal-footer">
              <button
                type="button"
                className="auth-submit"
                onClick={handleChangePassword}
                disabled={isChangingPassword}
              >
                {isChangingPassword ? '修改中...' : '确认修改'}
              </button>
              <button
                type="button"
                className="auth-link"
                onClick={() => {
                  setShowChangePassword(false);
                  setChangePasswordData({
                    oldPassword: '',
                    newPassword: '',
                    confirmNewPassword: '',
                  });
                  setChangePasswordError(null);
                }}
                disabled={isChangingPassword}
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
