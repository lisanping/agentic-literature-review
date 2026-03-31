import { create } from 'zustand';
import type { User } from '@/types/user';

const TOKEN_KEY = 'auth_access_token';
const REFRESH_KEY = 'auth_refresh_token';

interface AuthState {
    /** 当前用户 */
    user: User | null;
    /** 是否已认证 */
    isAuthenticated: boolean;
    /** 正在加载用户信息 */
    loading: boolean;

    /** 登录成功后设置 Token + 用户 */
    setAuth: (user: User, accessToken: string, refreshToken: string) => void;
    /** 仅更新用户信息 (不改 Token) */
    setUser: (user: User) => void;
    /** 登出 */
    clearAuth: () => void;
    /** 设置加载状态 */
    setLoading: (loading: boolean) => void;

    /** 获取存储的 access token */
    getAccessToken: () => string | null;
    /** 获取存储的 refresh token */
    getRefreshToken: () => string | null;
    /** 仅更新 token (刷新后) */
    updateTokens: (accessToken: string, refreshToken: string) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    user: null,
    isAuthenticated: !!localStorage.getItem(TOKEN_KEY),
    loading: false,

    setAuth: (user, accessToken, refreshToken) => {
        localStorage.setItem(TOKEN_KEY, accessToken);
        localStorage.setItem(REFRESH_KEY, refreshToken);
        set({ user, isAuthenticated: true });
    },

    setUser: (user) => set({ user }),

    clearAuth: () => {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_KEY);
        set({ user: null, isAuthenticated: false });
    },

    setLoading: (loading) => set({ loading }),

    getAccessToken: () => localStorage.getItem(TOKEN_KEY),
    getRefreshToken: () => localStorage.getItem(REFRESH_KEY),

    updateTokens: (accessToken, refreshToken) => {
        localStorage.setItem(TOKEN_KEY, accessToken);
        localStorage.setItem(REFRESH_KEY, refreshToken);
    },
}));
