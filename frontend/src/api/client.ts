import axios from 'axios';
import { message } from 'antd';

const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// ── Request interceptor: inject Bearer token ──
apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('auth_access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// ── Response interceptor: handle errors + token refresh ──
let isRefreshing = false;
let pendingRequests: Array<(token: string) => void> = [];

apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        if (!axios.isAxiosError(error) || !error.response) {
            message.error('网络错误，请检查连接');
            return Promise.reject(error);
        }

        const { status, data, config: originalConfig } = error.response;

        // Token expired — attempt refresh
        if (status === 401 && !originalConfig._retry && localStorage.getItem('auth_refresh_token')) {
            if (isRefreshing) {
                // Queue this request until refresh completes
                return new Promise((resolve) => {
                    pendingRequests.push((newToken: string) => {
                        originalConfig.headers.Authorization = `Bearer ${newToken}`;
                        resolve(apiClient(originalConfig));
                    });
                });
            }

            originalConfig._retry = true;
            isRefreshing = true;

            try {
                const refreshToken = localStorage.getItem('auth_refresh_token')!;
                const resp = await axios.post(
                    `${originalConfig.baseURL || ''}/api/v1/auth/refresh`,
                    { refresh_token: refreshToken },
                );
                const { access_token, refresh_token: newRefresh } = resp.data;

                localStorage.setItem('auth_access_token', access_token);
                localStorage.setItem('auth_refresh_token', newRefresh);

                // Retry queued requests
                pendingRequests.forEach((cb) => cb(access_token));
                pendingRequests = [];

                originalConfig.headers.Authorization = `Bearer ${access_token}`;
                return apiClient(originalConfig);
            } catch {
                // Refresh failed — clear auth and redirect to login
                localStorage.removeItem('auth_access_token');
                localStorage.removeItem('auth_refresh_token');
                window.location.href = '/login';
                return Promise.reject(error);
            } finally {
                isRefreshing = false;
            }
        }

        const detail = (data as { detail?: string })?.detail || '请求失败';

        switch (status) {
            case 401:
                // Already handled above, or no refresh token
                message.error('登录已过期，请重新登录');
                break;
            case 403:
                message.error('权限不足');
                break;
            case 404:
                message.error(`资源不存在: ${detail}`);
                break;
            case 409:
                message.error(`操作冲突: ${detail}`);
                break;
            case 422:
                message.error(`参数校验失败: ${detail}`);
                break;
            case 503:
                message.error('服务暂不可用，请稍后重试');
                break;
            default:
                message.error(detail);
        }
        return Promise.reject(error);
    },
);

// Extend AxiosRequestConfig to support _retry flag
declare module 'axios' {
    interface InternalAxiosRequestConfig {
        _retry?: boolean;
    }
}

export default apiClient;
