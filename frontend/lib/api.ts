/**
 * 封装对后端 REST API 的 fetch 调用。
 *
 * 职责：
 * - 注入 Authorization Bearer token
 * - 请求携带 Cookie（credentials: 'include'）
 * - 遇到 401 时自动用 Refresh Token Cookie 换取新 Access Token，并重试一次
 * - 提供 apiJSON 便捷方法，统一抛出 ApiError
 */

import { tokenStore } from './token';
import type { RefreshResponse } from './types';

/** 同一时刻只发一个 refresh 请求，防止并发重复刷新。 */
let _refreshPromise: Promise<string | null> | null = null;

/**
 * 用 Refresh Token Cookie 换取新的 Access Token。
 *
 * Returns:
 *     新 token 字符串，刷新失败返回 null。
 */
export async function tryRefresh(): Promise<string | null> {
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    try {
      const res = await fetch(`/api/v1/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        tokenStore.clear();
        return null;
      }
      const data: RefreshResponse = await res.json();
      tokenStore.set(data.access_token, data.expires_in);
      return data.access_token;
    } catch {
      tokenStore.clear();
      return null;
    } finally {
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
}

/**
 * 发起 fetch 请求，自动注入 token 并在 401 时尝试刷新后重试。
 *
 * Args:
 *     path: 以 / 开头的 API 路径，如 "/api/v1/auth/me"。
 *     init: 标准 RequestInit 选项。
 *
 * Returns:
 *     原生 Response 对象。
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const buildHeaders = (token: string | null): Headers => {
    const headers = new Headers(init.headers);
    if (token) headers.set('Authorization', `Bearer ${token}`);
    return headers;
  };

  const res = await fetch(path, {
    ...init,
    headers: buildHeaders(tokenStore.get()),
    credentials: 'include',
  });

  if (res.status !== 401) return res;

  // 401：尝试刷新，成功则重试一次
  const newToken = await tryRefresh();
  if (!newToken) return res;

  return fetch(path, {
    ...init,
    headers: buildHeaders(newToken),
    credentials: 'include',
  });
}

/**
 * 发起 JSON 请求，响应非 2xx 时抛出 ApiError。
 *
 * Args:
 *     path: API 路径。
 *     init: RequestInit 选项（Content-Type 默认为 application/json）。
 *
 * Returns:
 *     反序列化后的响应体。
 *
 * Raises:
 *     ApiError: HTTP 响应状态非 2xx。
 */
export async function apiJSON<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await apiFetch(path, { ...init, headers });

  if (res.ok) return res.json() as Promise<T>;

  const body = await res.json().catch(() => ({ detail: res.statusText }));
  throw new ApiError(res.status, body.detail ?? 'Request failed');
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}
