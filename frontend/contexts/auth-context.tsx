'use client';

/**
 * 全局认证上下文。
 *
 * 挂载时自动用 Refresh Token Cookie 换取 Access Token，
 * 恢复登录态后拉取 /auth/me 获取用户信息。
 */

import { createContext, useCallback, useContext, useEffect, useState } from 'react';

import { ApiError, apiJSON, apiFetch, tryRefresh } from '@/lib/api';
import { tokenStore } from '@/lib/token';
import type { LoginResponse, MeResponse, UserInfo } from '@/lib/types';

interface AuthContextValue {
  user: UserInfo | null;
  isAuthenticated: boolean;
  /** 首次启动时正在恢复登录态。 */
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // 启动时尝试用 Cookie 中的 Refresh Token 恢复会话
  useEffect(() => {
    (async () => {
      const token = await tryRefresh();
      if (token) {
        try {
          const me = await apiJSON<MeResponse>('/api/v1/auth/me');
          setUser(me);
          setIsAuthenticated(true);
        } catch {
          tokenStore.clear();
        }
      }
      setIsLoading(false);
    })();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = await apiJSON<LoginResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    tokenStore.set(data.access_token, data.expires_in);
    setUser(data.user);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiFetch('/api/v1/auth/logout', { method: 'POST' });
    } catch {
      // 登出时忽略服务端错误，本地状态照常清除
    } finally {
      tokenStore.clear();
      setUser(null);
      setIsAuthenticated(false);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * 获取当前认证上下文，必须在 AuthProvider 内部使用。
 *
 * Returns:
 *     AuthContextValue 对象。
 *
 * Raises:
 *     Error: 在 AuthProvider 外部调用时抛出。
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
