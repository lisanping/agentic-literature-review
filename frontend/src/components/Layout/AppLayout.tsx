import { Layout } from 'antd';
import { Outlet, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import StatusBar from './StatusBar';
import { useUIStore } from '@/stores/uiStore';
import { useProjects } from '@/hooks/useProjects';
import type { AgentProgress, TokenUsage } from '@/types';

const { Sider, Content, Footer } = Layout;

interface AppLayoutProps {
    /** Agent 进度 (由 workflowStore 驱动，阶段 4 接入) */
    agentProgress?: AgentProgress | null;
    /** Token 使用情况 */
    tokenUsage?: TokenUsage | null;
    /** 是否有活跃工作流 */
    workflowActive?: boolean;
}

export default function AppLayout({
    agentProgress = null,
    tokenUsage = null,
    workflowActive = false,
}: AppLayoutProps) {
    const navigate = useNavigate();
    const { sidebarCollapsed, setSidebarCollapsed } = useUIStore();
    const { projects, loading: projectsLoading, fetchProjects } = useProjects();

    return (
        <Layout style={{ minHeight: '100vh' }}>
            {/* 左侧栏 */}
            <Sider
                width={260}
                collapsedWidth={0}
                collapsible
                collapsed={sidebarCollapsed}
                onCollapse={setSidebarCollapsed}
                breakpoint="lg"
                style={{
                    background: '#fff',
                    borderRight: '1px solid #f0f0f0',
                    overflow: 'auto',
                }}
            >
                <Sidebar
                    projects={projects}
                    loading={projectsLoading}
                    onCreateProject={() => navigate('/')}
                    onRefresh={fetchProjects}
                />
            </Sider>

            {/* 右侧主区域 */}
            <Layout>
                {/* 主内容区 */}
                <Content style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ flex: 1, overflow: 'auto' }}>
                        <Outlet />
                    </div>
                </Content>

                {/* 底部状态栏 */}
                <Footer style={{ padding: 0 }}>
                    <StatusBar
                        agentProgress={agentProgress}
                        tokenUsage={tokenUsage}
                        active={workflowActive}
                    />
                </Footer>
            </Layout>
        </Layout>
    );
}
