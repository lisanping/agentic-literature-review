import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Menu, Button, Badge } from 'antd';
import {
    PlusOutlined,
    FolderOutlined,
    BookOutlined,
} from '@ant-design/icons';
import type { ProjectResponse } from '@/types';
import { PROJECT_STATUS_COLORS, PROJECT_STATUS_LABELS } from '@/utils/constants';
import { formatRelativeTime, truncate } from '@/utils/format';

interface SidebarProps {
    projects: ProjectResponse[];
    loading?: boolean;
    onCreateProject: () => void;
    onRefresh?: () => void;
}

export default function Sidebar({ projects, loading, onCreateProject, onRefresh }: SidebarProps) {
    const navigate = useNavigate();
    const location = useLocation();

    // 从 URL 提取当前选中的项目 ID
    const match = location.pathname.match(/^\/projects\/(.+)$/);
    const selectedKey = match ? match[1] : '';

    // 首次挂载时加载项目列表
    useEffect(() => {
        onRefresh?.();
    }, [onRefresh]);

    const menuItems = projects.map((project) => ({
        key: project.id,
        icon: <FolderOutlined />,
        label: (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>{truncate(project.title || project.user_query, 18)}</span>
                <Badge
                    status={PROJECT_STATUS_COLORS[project.status] as 'default' | 'processing' | 'success' | 'error' | 'warning'}
                    text=""
                    title={PROJECT_STATUS_LABELS[project.status]}
                />
            </div>
        ),
    }));

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* Logo */}
            <div
                style={{
                    padding: '16px',
                    textAlign: 'center',
                    borderBottom: '1px solid #f0f0f0',
                }}
            >
                <BookOutlined style={{ fontSize: 20, marginRight: 8, color: '#1677ff' }} />
                <span style={{ fontSize: 15, fontWeight: 600 }}>文献综述助手</span>
            </div>

            {/* 新建项目按钮 */}
            <div style={{ padding: '12px 16px 4px' }}>
                <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    block
                    onClick={onCreateProject}
                >
                    新建项目
                </Button>
            </div>

            {/* 项目列表 */}
            <div style={{ flex: 1, overflow: 'auto' }}>
                <Menu
                    mode="inline"
                    selectedKeys={selectedKey ? [selectedKey] : []}
                    items={menuItems}
                    onClick={({ key }) => navigate(`/projects/${key}`)}
                    style={{ border: 'none' }}
                />
                {!loading && projects.length === 0 && (
                    <div style={{ padding: '24px 16px', color: '#999', textAlign: 'center', fontSize: 13 }}>
                        暂无项目，点击上方按钮创建
                    </div>
                )}
            </div>

            {/* 底部：最近活动时间（可选） */}
            {projects.length > 0 && (
                <div
                    style={{
                        padding: '8px 16px',
                        borderTop: '1px solid #f0f0f0',
                        fontSize: 12,
                        color: '#999',
                    }}
                >
                    最近活动: {formatRelativeTime(projects[0]!.updated_at)}
                </div>
            )}
        </div>
    );
}
