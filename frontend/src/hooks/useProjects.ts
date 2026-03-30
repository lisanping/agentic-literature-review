import { useCallback } from 'react';
import { useProjectStore } from '@/stores/projectStore';
import * as projectsApi from '@/api/projects';
import type { ProjectCreate } from '@/types';

/**
 * 项目 CRUD 操作 Hook
 *
 * 封装 API 调用 + Store 同步，组件只需调用 action 即可。
 */
export function useProjects() {
    const {
        projects,
        loading,
        setProjects,
        setLoading,
        addProject,
        removeProject,
        updateProject,
        setCurrentProject,
    } = useProjectStore();

    /** 加载项目列表 */
    const fetchProjects = useCallback(async () => {
        setLoading(true);
        try {
            const res = await projectsApi.listProjects({ size: 100 });
            setProjects(res.data.items);
        } finally {
            setLoading(false);
        }
    }, [setLoading, setProjects]);

    /** 创建项目 */
    const createProject = useCallback(
        async (data: ProjectCreate) => {
            const res = await projectsApi.createProject(data);
            addProject(res.data);
            return res.data;
        },
        [addProject],
    );

    /** 删除项目 */
    const deleteProject = useCallback(
        async (projectId: string) => {
            await projectsApi.deleteProject(projectId);
            removeProject(projectId);
        },
        [removeProject],
    );

    /** 获取项目详情并设为当前项目 */
    const fetchProject = useCallback(
        async (projectId: string) => {
            const res = await projectsApi.getProject(projectId);
            setCurrentProject(res.data);
            updateProject(res.data);
            return res.data;
        },
        [setCurrentProject, updateProject],
    );

    return {
        projects,
        loading,
        fetchProjects,
        createProject,
        deleteProject,
        fetchProject,
    };
}
