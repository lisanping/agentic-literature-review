import { useNavigate } from 'react-router-dom';
import { Dropdown, Avatar, Space, Typography } from 'antd';
import {
    UserOutlined,
    SettingOutlined,
    LogoutOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { useAuthStore } from '@/stores/authStore';
import * as authApi from '@/api/auth';

const { Text } = Typography;

export default function UserMenu() {
    const navigate = useNavigate();
    const { user, clearAuth, getRefreshToken } = useAuthStore();

    if (!user) return null;

    const handleLogout = async () => {
        const refreshToken = getRefreshToken();
        if (refreshToken) {
            try {
                await authApi.logout(refreshToken);
            } catch {
                // Ignore logout errors — clear local state anyway
            }
        }
        clearAuth();
        navigate('/login');
    };

    const items: MenuProps['items'] = [
        {
            key: 'profile',
            icon: <UserOutlined />,
            label: user.email,
            disabled: true,
        },
        { type: 'divider' },
        {
            key: 'settings',
            icon: <SettingOutlined />,
            label: '个人设置',
            onClick: () => navigate('/settings'),
        },
        { type: 'divider' },
        {
            key: 'logout',
            icon: <LogoutOutlined />,
            label: '退出登录',
            danger: true,
            onClick: handleLogout,
        },
    ];

    return (
        <Dropdown menu={{ items }} trigger={['click']} placement="bottomRight">
            <Space style={{ cursor: 'pointer', padding: '0 12px' }}>
                <Avatar
                    size="small"
                    src={user.avatar_url}
                    icon={<UserOutlined />}
                    style={{ backgroundColor: '#1677ff' }}
                />
                <Text style={{ maxWidth: 120 }} ellipsis>
                    {user.username}
                </Text>
            </Space>
        </Dropdown>
    );
}
