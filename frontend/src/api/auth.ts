import apiClient from './client';
import type {
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    User,
    UserUpdateRequest,
    PasswordChangeRequest,
} from '@/types/user';

/** 用户注册 */
export function register(data: RegisterRequest) {
    return apiClient.post<TokenResponse>('/api/v1/auth/register', data);
}

/** 用户登录 */
export function login(data: LoginRequest) {
    return apiClient.post<TokenResponse>('/api/v1/auth/login', data);
}

/** 刷新 Token */
export function refreshToken(refresh_token: string) {
    return apiClient.post<TokenResponse>('/api/v1/auth/refresh', { refresh_token });
}

/** 登出 */
export function logout(refresh_token: string) {
    return apiClient.post('/api/v1/auth/logout', { refresh_token });
}

/** 获取当前用户信息 */
export function getMe() {
    return apiClient.get<User>('/api/v1/users/me');
}

/** 更新当前用户信息 */
export function updateMe(data: UserUpdateRequest) {
    return apiClient.patch<User>('/api/v1/users/me', data);
}

/** 修改密码 */
export function changePassword(data: PasswordChangeRequest) {
    return apiClient.put('/api/v1/users/me/password', data);
}
