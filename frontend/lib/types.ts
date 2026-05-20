/**
 * 与后端 Pydantic Schema 对应的前端类型定义。
 */

export interface UserInfo {
  id: number;
  username: string;
  display_name: string;
  department_id: number | null;
  department_name: string | null;
  role: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserInfo;
  require_password_change: boolean;
}

export interface RefreshResponse {
  access_token: string;
  expires_in: number;
}

export interface MeResponse {
  id: number;
  username: string;
  display_name: string;
  department_id: number | null;
  department_name: string | null;
  role: string;
  created_at: string;
}
