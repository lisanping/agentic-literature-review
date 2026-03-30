import { create } from 'zustand';
import type { ProjectResponse } from '@/types';

interface ProjectState {
    /** 项目列表 */
    projects: ProjectResponse[];
    /** 列表加载中 */
    loading: boolean;
    /** 当前选中的项目 */
    currentProject: ProjectResponse | null;

    /** 设置项目列表 */
    setProjects: (projects: ProjectResponse[]) => void;
    /** 设置加载状态 */
    setLoading: (loading: boolean) => void;
    /** 设置当前项目 */
    setCurrentProject: (project: ProjectResponse | null) => void;
    /** 添加项目到列表头部 */
    addProject: (project: ProjectResponse) => void;
    /** 从列表中移除项目 */
    removeProject: (projectId: string) => void;
    /** 更新列表中某个项目 */
    updateProject: (project: ProjectResponse) => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
    projects: [],
    loading: false,
    currentProject: null,

    setProjects: (projects) => set({ projects }),
    setLoading: (loading) => set({ loading }),
    setCurrentProject: (currentProject) => set({ currentProject }),

    addProject: (project) =>
        set((state) => ({ projects: [project, ...state.projects] })),

    removeProject: (projectId) =>
        set((state) => ({
            projects: state.projects.filter((p) => p.id !== projectId),
            currentProject:
                state.currentProject?.id === projectId ? null : state.currentProject,
        })),

    updateProject: (project) =>
        set((state) => ({
            projects: state.projects.map((p) => (p.id === project.id ? project : p)),
            currentProject:
                state.currentProject?.id === project.id ? project : state.currentProject,
        })),
}));
