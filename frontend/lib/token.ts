/**
 * 前端内存级 Access Token 存储。
 *
 * 不写入 localStorage / sessionStorage，防止 XSS 窃取。
 * 刷新页面后 token 丢失，由 auth-context 启动时自动通过 Refresh Token Cookie 换取。
 */

let _token: string | null = null;
let _expiresAt = 0;

export const tokenStore = {
  /** 写入 token，expiresIn 单位为秒，提前 30 秒视为过期。 */
  set(token: string, expiresIn: number): void {
    _token = token;
    _expiresAt = Date.now() + (expiresIn - 30) * 1000;
  },

  /** 返回未过期的 token，否则返回 null。 */
  get(): string | null {
    if (_token && Date.now() < _expiresAt) return _token;
    return null;
  },

  clear(): void {
    _token = null;
    _expiresAt = 0;
  },
};
