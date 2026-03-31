import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Card, Form, Input, Button, Typography, Divider, message } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined, ExperimentOutlined } from '@ant-design/icons';
import * as authApi from '@/api/auth';
import { useAuthStore } from '@/stores/authStore';

const { Title, Text } = Typography;

export default function LoginPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const setAuth = useAuthStore((s) => s.setAuth);

    const [mode, setMode] = useState<'login' | 'register'>('login');
    const [loading, setLoading] = useState(false);
    const [form] = Form.useForm();

    const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

    const handleSubmit = async (values: {
        email: string;
        password: string;
        username?: string;
    }) => {
        setLoading(true);
        try {
            let tokenResp;
            if (mode === 'register') {
                const resp = await authApi.register({
                    email: values.email,
                    username: values.username!,
                    password: values.password,
                });
                tokenResp = resp.data;
                message.success('注册成功');
            } else {
                const resp = await authApi.login({
                    email: values.email,
                    password: values.password,
                });
                tokenResp = resp.data;
            }

            // Fetch user info
            const meResp = await authApi.getMe();
            setAuth(meResp.data, tokenResp.access_token, tokenResp.refresh_token);
            navigate(from, { replace: true });
        } catch {
            // Error handled by axios interceptor
        } finally {
            setLoading(false);
        }
    };

    const toggleMode = () => {
        setMode(mode === 'login' ? 'register' : 'login');
        form.resetFields();
    };

    return (
        <div
            style={{
                minHeight: '100vh',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: '#f5f5f5',
            }}
        >
            <Card style={{ width: 400, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
                <div style={{ textAlign: 'center', marginBottom: 24 }}>
                    <ExperimentOutlined
                        style={{ fontSize: 40, color: '#1677ff', marginBottom: 8 }}
                    />
                    <Title level={3} style={{ marginBottom: 4 }}>
                        文献综述智能助手
                    </Title>
                    <Text type="secondary">
                        {mode === 'login' ? '登录您的账号' : '创建新账号'}
                    </Text>
                </div>

                <Form form={form} onFinish={handleSubmit} layout="vertical" size="large">
                    <Form.Item
                        name="email"
                        rules={[
                            { required: true, message: '请输入邮箱' },
                            { type: 'email', message: '请输入有效邮箱' },
                        ]}
                    >
                        <Input prefix={<MailOutlined />} placeholder="邮箱" autoComplete="email" />
                    </Form.Item>

                    {mode === 'register' && (
                        <Form.Item
                            name="username"
                            rules={[
                                { required: true, message: '请输入用户名' },
                                { min: 2, max: 50, message: '用户名长度 2-50 个字符' },
                            ]}
                        >
                            <Input
                                prefix={<UserOutlined />}
                                placeholder="用户名"
                                autoComplete="username"
                            />
                        </Form.Item>
                    )}

                    <Form.Item
                        name="password"
                        rules={[
                            { required: true, message: '请输入密码' },
                            { min: 8, message: '密码至少 8 个字符' },
                        ]}
                    >
                        <Input.Password
                            prefix={<LockOutlined />}
                            placeholder="密码"
                            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                        />
                    </Form.Item>

                    <Form.Item style={{ marginBottom: 12 }}>
                        <Button type="primary" htmlType="submit" loading={loading} block>
                            {mode === 'login' ? '登录' : '注册'}
                        </Button>
                    </Form.Item>
                </Form>

                <Divider plain>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        {mode === 'login' ? '还没有账号？' : '已有账号？'}
                    </Text>
                </Divider>

                <Button type="link" onClick={toggleMode} block>
                    {mode === 'login' ? '注册新账号' : '返回登录'}
                </Button>
            </Card>
        </div>
    );
}
