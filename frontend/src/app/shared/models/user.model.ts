export interface User {
  id: string;
  username: string;
  email: string | null;
  display_name: string | null;
  auth_provider: string;
  is_active: boolean;
  is_admin: boolean;
  roles: string[];
  last_login: string | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}
