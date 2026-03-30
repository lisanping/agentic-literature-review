import axios from 'axios';
import { message } from 'antd';

const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (axios.isAxiosError(error) && error.response) {
            const { status, data } = error.response;
            const detail = (data as { detail?: string })?.detail || '请求失败';

            switch (status) {
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
        } else {
            message.error('网络错误，请检查连接');
        }
        return Promise.reject(error);
    },
);

export default apiClient;
