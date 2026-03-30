import { create } from 'zustand';

interface UIState {
    /** 侧栏是否折叠 */
    sidebarCollapsed: boolean;
    /** 切换侧栏折叠状态 */
    toggleSidebar: () => void;
    /** 设置侧栏折叠状态 */
    setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
    sidebarCollapsed: false,
    toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
    setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
}));
