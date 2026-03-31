import { create } from 'zustand';

interface VisualizationStoreState {
    /** Currently selected node/paper ID in graph or timeline */
    selectedNodeId: string | null;
    /** Highlighted cluster IDs — empty set means show all */
    highlightedClusters: Set<string>;
    /** Time range filter */
    timeRange: [number, number] | null;
    /** Search query for graph filtering */
    searchQuery: string;
    /** Active visualization tab */
    activeTab: 'graph' | 'timeline' | 'trends';

    // ── Actions ──
    selectNode: (id: string | null) => void;
    toggleCluster: (clusterId: string) => void;
    setHighlightedClusters: (ids: Set<string>) => void;
    setTimeRange: (range: [number, number] | null) => void;
    setSearchQuery: (query: string) => void;
    setActiveTab: (tab: 'graph' | 'timeline' | 'trends') => void;
    reset: () => void;
}

export const useVisualizationStore = create<VisualizationStoreState>((set) => ({
    selectedNodeId: null,
    highlightedClusters: new Set<string>(),
    timeRange: null,
    searchQuery: '',
    activeTab: 'graph',

    selectNode: (id) => set({ selectedNodeId: id }),

    toggleCluster: (clusterId) =>
        set((state) => {
            const next = new Set(state.highlightedClusters);
            if (next.has(clusterId)) {
                next.delete(clusterId);
            } else {
                next.add(clusterId);
            }
            return { highlightedClusters: next };
        }),

    setHighlightedClusters: (ids) => set({ highlightedClusters: ids }),
    setTimeRange: (range) => set({ timeRange: range }),
    setSearchQuery: (query) => set({ searchQuery: query }),
    setActiveTab: (tab) => set({ activeTab: tab }),

    reset: () =>
        set({
            selectedNodeId: null,
            highlightedClusters: new Set<string>(),
            timeRange: null,
            searchQuery: '',
            activeTab: 'graph',
        }),
}));
