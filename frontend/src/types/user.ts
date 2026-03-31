/** User and authentication types — v0.4 */

export interface User {
    id: string;
    email: string;
    username: string;
    role: 'admin' | 'user';
    is_active: boolean;
    avatar_url: string | null;
    preferences: Record<string, unknown>;
    created_at: string;
    last_login_at: string | null;
}

export interface LoginRequest {
    email: string;
    password: string;
}

export interface RegisterRequest {
    email: string;
    username: string;
    password: string;
}

export interface TokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
}

export interface PasswordChangeRequest {
    current_password: string;
    new_password: string;
}

export interface UserUpdateRequest {
    username?: string;
    avatar_url?: string | null;
    preferences?: Record<string, unknown>;
}
