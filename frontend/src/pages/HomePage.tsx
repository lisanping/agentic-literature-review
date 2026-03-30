import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Input,
    Button,
    Radio,
    Upload,
    Card,
    List,
    Badge,
    Space,
    Typography,
    message,
    Alert,
} from 'antd';
import {
    SearchOutlined,
    UploadOutlined,
    FileTextOutlined,
    ClockCircleOutlined,
    ExperimentOutlined,
    DeleteOutlined,
    PlayCircleOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd';
import { useProjects } from '@/hooks/useProjects';
import { uploadPaperFile } from '@/api/papers';
import { OutputType, ProjectStatus } from '@/types/enums';
import type { ProjectResponse } from '@/types';
import {
    OUTPUT_TYPE_LABELS,
    PROJECT_STATUS_LABELS,
    PROJECT_STATUS_COLORS,
    MVP_OUTPUT_TYPES,
} from '@/utils/constants';
import { formatRelativeTime } from '@/utils/format';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

/** 是否为进行中状态 (可恢复) */
function isInProgress(status: ProjectStatus): boolean {
    return ![
        ProjectStatus.CREATED,
        ProjectStatus.COMPLETED,
        ProjectStatus.FAILED,
        ProjectStatus.CANCELLED,
    ].includes(status);
}

export default function HomePage() {
    const navigate = useNavigate();
    const { projects, loading, createProject, deleteProject } = useProjects();

    const [userQuery, setUserQuery] = useState('');
    const [outputType, setOutputType] = useState<OutputType>(OutputType.FULL_REVIEW);
    const [fileList, setFileList] = useState<UploadFile[]>([]);
    const [creating, setCreating] = useState(false);

    // 找出可恢复的项目
    const inProgressProjects = projects.filter((p) => isInProgress(p.status as ProjectStatus));

    /** 创建项目并跳转 */
    const handleCreate = async () => {
        if (!userQuery.trim()) {
            message.warning('请输入研究问题');
            return;
        }

        setCreating(true);
        try {
            const project = await createProject({
                user_query: userQuery.trim(),
                output_types: [outputType],
            });

            // 如果有上传文件，逐个上传
            for (const file of fileList) {
                if (file.originFileObj) {
                    try {
                        await uploadPaperFile(project.id, file.originFileObj);
                    } catch {
                        message.warning(`文件 ${file.name} 上传失败，可稍后重试`);
                    }
                }
            }

            message.success('项目创建成功');
            navigate(`/projects/${project.id}`);
        } finally {
            setCreating(false);
        }
    };

    /** 删除项目 */
    const handleDelete = async (e: React.MouseEvent, project: ProjectResponse) => {
        e.stopPropagation();
        try {
            await deleteProject(project.id);
            message.success('项目已删除');
        } catch {
            // error handled by axios interceptor
        }
    };

    return (
        <div style={{ maxWidth: 800, margin: '0 auto', padding: '40px 24px' }}>
            {/* 标题 */}
            <div style={{ textAlign: 'center', marginBottom: 40 }}>
                <ExperimentOutlined style={{ fontSize: 48, color: '#1677ff', marginBottom: 16 }} />
                <Title level={2} style={{ marginBottom: 8 }}>
                    文献综述智能助手
                </Title>
                <Paragraph type="secondary">
                    输入研究问题，AI 自动完成检索、精读、分析和写作
                </Paragraph>
            </div>

            {/* 可恢复项目提示 */}
            {inProgressProjects.length > 0 && (
                <Alert
                    type="info"
                    showIcon
                    icon={<PlayCircleOutlined />}
                    style={{ marginBottom: 24 }}
                    message={`发现 ${inProgressProjects.length} 个进行中的项目`}
                    description={
                        <Space direction="vertical" size={4} style={{ width: '100%' }}>
                            {inProgressProjects.slice(0, 3).map((p) => (
                                <Button
                                    key={p.id}
                                    type="link"
                                    size="small"
                                    onClick={() => navigate(`/projects/${p.id}`)}
                                    style={{ padding: 0, height: 'auto' }}
                                >
                                    {p.title || p.user_query} — {PROJECT_STATUS_LABELS[p.status]}
                                </Button>
                            ))}
                        </Space>
                    }
                />
            )}

            {/* 研究问题输入 */}
            <Card style={{ marginBottom: 24 }}>
                <TextArea
                    placeholder="请描述您的研究问题...&#10;&#10;例如：&#10;· 大语言模型在代码生成中的应用&#10;· 深度学习在医学影像中的最新进展"
                    autoSize={{ minRows: 4, maxRows: 8 }}
                    value={userQuery}
                    onChange={(e) => setUserQuery(e.target.value)}
                    maxLength={2000}
                    showCount
                    style={{ marginBottom: 16 }}
                />

                {/* 输出类型选择 */}
                <div style={{ marginBottom: 16 }}>
                    <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                        输出类型
                    </Text>
                    <Radio.Group
                        value={outputType}
                        onChange={(e) => setOutputType(e.target.value as OutputType)}
                    >
                        {MVP_OUTPUT_TYPES.map((type) => (
                            <Radio.Button key={type} value={type}>
                                {OUTPUT_TYPE_LABELS[type]}
                            </Radio.Button>
                        ))}
                    </Radio.Group>
                </div>

                {/* 文件上传 */}
                <div style={{ marginBottom: 16 }}>
                    <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                        上传文件（可选）
                    </Text>
                    <Upload
                        fileList={fileList}
                        onChange={({ fileList: newList }) => setFileList(newList)}
                        beforeUpload={() => false}
                        accept=".pdf,.bib,.ris"
                        multiple
                    >
                        <Button icon={<UploadOutlined />}>选择文件 (PDF / .bib / .ris)</Button>
                    </Upload>
                </div>

                {/* 开始按钮 */}
                <Button
                    type="primary"
                    size="large"
                    icon={<SearchOutlined />}
                    onClick={handleCreate}
                    loading={creating}
                    disabled={!userQuery.trim()}
                    block
                >
                    开始文献综述
                </Button>
            </Card>

            {/* 最近项目列表 */}
            {projects.length > 0 && (
                <div>
                    <Title level={5} style={{ marginBottom: 12 }}>
                        <ClockCircleOutlined style={{ marginRight: 8 }} />
                        最近项目
                    </Title>
                    <List
                        loading={loading}
                        dataSource={projects.slice(0, 10)}
                        renderItem={(project) => (
                            <List.Item
                                style={{ cursor: 'pointer' }}
                                onClick={() => navigate(`/projects/${project.id}`)}
                                actions={[
                                    <Button
                                        key="delete"
                                        type="text"
                                        danger
                                        size="small"
                                        icon={<DeleteOutlined />}
                                        onClick={(e) => handleDelete(e, project)}
                                    />,
                                ]}
                            >
                                <List.Item.Meta
                                    avatar={<FileTextOutlined style={{ fontSize: 20, color: '#1677ff' }} />}
                                    title={project.title || project.user_query}
                                    description={
                                        <Space size="middle">
                                            <Badge
                                                status={
                                                    PROJECT_STATUS_COLORS[project.status] as
                                                    | 'default'
                                                    | 'processing'
                                                    | 'success'
                                                    | 'error'
                                                    | 'warning'
                                                }
                                                text={PROJECT_STATUS_LABELS[project.status]}
                                            />
                                            <Text type="secondary">{project.paper_count} 篇论文</Text>
                                            <Text type="secondary">{formatRelativeTime(project.updated_at)}</Text>
                                        </Space>
                                    }
                                />
                            </List.Item>
                        )}
                    />
                </div>
            )}
        </div>
    );
}
