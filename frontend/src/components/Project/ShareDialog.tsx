import { useState, useEffect } from 'react';
import { Modal, Form, Input, Select, Table, Button, Space, message, Popconfirm } from 'antd';
import { UserAddOutlined, DeleteOutlined } from '@ant-design/icons';
import * as sharesApi from '@/api/shares';
import type { ShareResponse } from '@/types/share';

interface ShareDialogProps {
    projectId: string;
    open: boolean;
    onClose: () => void;
}

export default function ShareDialog({ projectId, open, onClose }: ShareDialogProps) {
    const [shares, setShares] = useState<ShareResponse[]>([]);
    const [loading, setLoading] = useState(false);
    const [adding, setAdding] = useState(false);
    const [form] = Form.useForm();

    const fetchShares = async () => {
        setLoading(true);
        try {
            const resp = await sharesApi.listShares(projectId);
            setShares(resp.data);
        } catch {
            // Error handled by interceptor
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (open) fetchShares();
    }, [open, projectId]);

    const handleAdd = async (values: { email: string; permission: 'viewer' | 'collaborator' }) => {
        setAdding(true);
        try {
            await sharesApi.shareProject(projectId, values);
            message.success('已分享');
            form.resetFields();
            fetchShares();
        } catch {
            // Error handled by interceptor
        } finally {
            setAdding(false);
        }
    };

    const handleRevoke = async (shareId: string) => {
        try {
            await sharesApi.revokeShare(projectId, shareId);
            message.success('已撤销分享');
            fetchShares();
        } catch {
            // Error handled by interceptor
        }
    };

    const handlePermissionChange = async (shareId: string, permission: 'viewer' | 'collaborator') => {
        try {
            await sharesApi.updateShare(projectId, shareId, { permission });
            message.success('权限已更新');
            fetchShares();
        } catch {
            // Error handled by interceptor
        }
    };

    const columns = [
        {
            title: '用户',
            key: 'user',
            render: (_: unknown, record: ShareResponse) => (
                <Space direction="vertical" size={0}>
                    <span>{record.username}</span>
                    <span style={{ fontSize: 12, color: '#999' }}>{record.email}</span>
                </Space>
            ),
        },
        {
            title: '权限',
            dataIndex: 'permission',
            key: 'permission',
            width: 140,
            render: (permission: string, record: ShareResponse) => (
                <Select
                    value={permission as 'viewer' | 'collaborator'}
                    size="small"
                    style={{ width: 120 }}
                    onChange={(val: 'viewer' | 'collaborator') => handlePermissionChange(record.id, val)}
                    options={[
                        { value: 'viewer', label: '只读' },
                        { value: 'collaborator', label: '协作者' },
                    ]}
                />
            ),
        },
        {
            title: '',
            key: 'actions',
            width: 60,
            render: (_: unknown, record: ShareResponse) => (
                <Popconfirm
                    title="确认撤销此分享？"
                    onConfirm={() => handleRevoke(record.id)}
                    okText="撤销"
                    cancelText="取消"
                >
                    <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                </Popconfirm>
            ),
        },
    ];

    return (
        <Modal
            title="项目分享"
            open={open}
            onCancel={onClose}
            footer={null}
            width={520}
        >
            {/* 添加分享表单 */}
            <Form
                form={form}
                onFinish={handleAdd}
                layout="inline"
                style={{ marginBottom: 16 }}
                initialValues={{ permission: 'viewer' }}
            >
                <Form.Item
                    name="email"
                    rules={[
                        { required: true, message: '请输入邮箱' },
                        { type: 'email', message: '请输入有效邮箱' },
                    ]}
                    style={{ flex: 1 }}
                >
                    <Input placeholder="输入用户邮箱" />
                </Form.Item>
                <Form.Item name="permission">
                    <Select
                        style={{ width: 100 }}
                        options={[
                            { value: 'viewer', label: '只读' },
                            { value: 'collaborator', label: '协作者' },
                        ]}
                    />
                </Form.Item>
                <Form.Item>
                    <Button
                        type="primary"
                        htmlType="submit"
                        loading={adding}
                        icon={<UserAddOutlined />}
                    >
                        添加
                    </Button>
                </Form.Item>
            </Form>

            {/* 已分享列表 */}
            <Table
                dataSource={shares}
                columns={columns}
                rowKey="id"
                loading={loading}
                pagination={false}
                size="small"
                locale={{ emptyText: '暂无分享' }}
            />
        </Modal>
    );
}
