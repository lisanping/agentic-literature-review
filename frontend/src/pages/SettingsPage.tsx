import { useState } from 'react';
import { Card, Form, Input, Button, Typography, message, Descriptions } from 'antd';
import { UserOutlined, LockOutlined, SaveOutlined } from '@ant-design/icons';
import { useAuthStore } from '@/stores/authStore';
import * as authApi from '@/api/auth';

const { Title } = Typography;

export default function SettingsPage() {
    const { user, setUser } = useAuthStore();
    const [profileForm] = Form.useForm();
    const [passwordForm] = Form.useForm();
    const [profileLoading, setProfileLoading] = useState(false);
    const [passwordLoading, setPasswordLoading] = useState(false);

    if (!user) return null;

    const handleProfileUpdate = async (values: { username: string }) => {
        setProfileLoading(true);
        try {
            const resp = await authApi.updateMe({ username: values.username });
            setUser(resp.data);
            message.success('个人信息已更新');
        } catch {
            // Error handled by interceptor
        } finally {
            setProfileLoading(false);
        }
    };

    const handlePasswordChange = async (values: {
        current_password: string;
        new_password: string;
    }) => {
        setPasswordLoading(true);
        try {
            await authApi.changePassword({
                current_password: values.current_password,
                new_password: values.new_password,
            });
            message.success('密码已修改');
            passwordForm.resetFields();
        } catch {
            // Error handled by interceptor
        } finally {
            setPasswordLoading(false);
        }
    };

    return (
        <div style={{ maxWidth: 600, margin: '0 auto', padding: '40px 24px' }}>
            <Title level={3}>
                <UserOutlined style={{ marginRight: 8 }} />
                个人设置
            </Title>

            {/* 账号信息 */}
            <Card style={{ marginBottom: 24 }}>
                <Descriptions title="账号信息" column={1} size="small">
                    <Descriptions.Item label="邮箱">{user.email}</Descriptions.Item>
                    <Descriptions.Item label="角色">
                        {user.role === 'admin' ? '管理员' : '普通用户'}
                    </Descriptions.Item>
                    <Descriptions.Item label="注册时间">
                        {new Date(user.created_at).toLocaleDateString('zh-CN')}
                    </Descriptions.Item>
                </Descriptions>
            </Card>

            {/* 修改用户名 */}
            <Card title="修改资料" style={{ marginBottom: 24 }}>
                <Form
                    form={profileForm}
                    onFinish={handleProfileUpdate}
                    layout="vertical"
                    initialValues={{ username: user.username }}
                >
                    <Form.Item
                        name="username"
                        label="用户名"
                        rules={[
                            { required: true, message: '请输入用户名' },
                            { min: 2, max: 50, message: '2-50 个字符' },
                        ]}
                    >
                        <Input prefix={<UserOutlined />} />
                    </Form.Item>
                    <Form.Item>
                        <Button
                            type="primary"
                            htmlType="submit"
                            loading={profileLoading}
                            icon={<SaveOutlined />}
                        >
                            保存
                        </Button>
                    </Form.Item>
                </Form>
            </Card>

            {/* 修改密码 */}
            <Card title="修改密码">
                <Form form={passwordForm} onFinish={handlePasswordChange} layout="vertical">
                    <Form.Item
                        name="current_password"
                        label="当前密码"
                        rules={[{ required: true, message: '请输入当前密码' }]}
                    >
                        <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
                    </Form.Item>
                    <Form.Item
                        name="new_password"
                        label="新密码"
                        rules={[
                            { required: true, message: '请输入新密码' },
                            { min: 8, message: '至少 8 个字符' },
                        ]}
                    >
                        <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
                    </Form.Item>
                    <Form.Item
                        name="confirm_password"
                        label="确认新密码"
                        dependencies={['new_password']}
                        rules={[
                            { required: true, message: '请确认新密码' },
                            ({ getFieldValue }) => ({
                                validator(_, value) {
                                    if (!value || getFieldValue('new_password') === value) {
                                        return Promise.resolve();
                                    }
                                    return Promise.reject(new Error('两次密码不一致'));
                                },
                            }),
                        ]}
                    >
                        <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
                    </Form.Item>
                    <Form.Item>
                        <Button
                            type="primary"
                            htmlType="submit"
                            loading={passwordLoading}
                            icon={<LockOutlined />}
                        >
                            修改密码
                        </Button>
                    </Form.Item>
                </Form>
            </Card>
        </div>
    );
}
