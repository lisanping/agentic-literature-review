/** Visualization types — Knowledge Graph, Timeline, Trends — v0.4 */

// ── Knowledge Graph ──

/** Graph node representing a paper */
export interface GraphNode {
    id: string;
    title: string;
    authors: string[];
    year: number | null;
    citations_count: number;
    cluster_id: string | null;
    cluster_name: string | null;
    /** Node position (set by D3 simulation) */
    x?: number;
    y?: number;
    fx?: number | null;
    fy?: number | null;
}

/** Graph edge representing a citation relationship */
export interface GraphEdge {
    source: string | GraphNode;
    target: string | GraphNode;
    relation_type: string;
    weight: number;
}

/** Complete graph data for D3 rendering */
export interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
    clusters: ClusterInfo[];
}

/** Cluster metadata for legend */
export interface ClusterInfo {
    id: string;
    name: string;
    color: string;
    paper_count: number;
}

// ── Timeline ──

/** Timeline event */
export interface TimelineEvent {
    year: number;
    paper_count: number;
    paper_ids: string[];
    papers: TimelinePaper[];
    milestone: string | null;
}

/** Simplified paper info for timeline */
export interface TimelinePaper {
    id: string;
    title: string;
    authors: string[];
    citations_count: number;
}

// ── Visualization State ──

/** Shared visualization interaction state */
export interface VisualizationState {
    /** Currently selected node/paper ID */
    selectedNodeId: string | null;
    /** Currently highlighted cluster IDs (empty = show all) */
    highlightedClusters: Set<string>;
    /** Time range filter [start, end] */
    timeRange: [number, number] | null;
    /** Search query for graph node matching */
    searchQuery: string;
    /** Active visualization tab */
    activeTab: 'graph' | 'timeline' | 'trends';
}

/** Default cluster color palette */
export const CLUSTER_COLORS = [
    '#1677ff', '#52c41a', '#fa8c16', '#722ed1', '#eb2f96',
    '#13c2c2', '#faad14', '#f5222d', '#2f54eb', '#a0d911',
    '#597ef7', '#9254de', '#ff7a45', '#36cfc9', '#ff85c0',
];
