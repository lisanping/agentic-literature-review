import { useEffect, useCallback, useRef } from 'react';
import * as d3 from 'd3';
import { Typography } from 'antd';
import type { GraphData, GraphNode, GraphEdge } from '@/types/visualization';
import { CLUSTER_COLORS } from '@/types/visualization';
import { useVisualizationStore } from '@/stores/visualizationStore';

const { Text } = Typography;

interface KnowledgeGraphProps {
    data: GraphData;
    width?: number;
    height?: number;
}

/** D3 force-directed knowledge graph */
export default function KnowledgeGraph({ data, width = 800, height = 600 }: KnowledgeGraphProps) {
    const svgRef = useRef<SVGSVGElement>(null);
    const simulationRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(null);
    const { selectedNodeId, selectNode, highlightedClusters, searchQuery } = useVisualizationStore();

    const clusterColorMap = useCallback(
        (clusterId: string | null): string => {
            if (!clusterId) return '#999';
            const idx = data.clusters.findIndex((c) => c.id === clusterId);
            return CLUSTER_COLORS[idx % CLUSTER_COLORS.length] ?? '#999';
        },
        [data.clusters],
    );

    useEffect(() => {
        if (!svgRef.current || !data.nodes.length) return;

        const svg = d3.select(svgRef.current);
        svg.selectAll('*').remove();

        // ── Scales ──
        const citationExtent = d3.extent(data.nodes, (d) => d.citations_count) as [number, number];
        const sizeScale = d3
            .scaleSqrt()
            .domain([citationExtent[0] || 0, citationExtent[1] || 1])
            .range([4, 20]);

        // ── Container with zoom ──
        const g = svg.append('g');
        const zoom = d3
            .zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.2, 5])
            .on('zoom', (event) => g.attr('transform', event.transform));
        svg.call(zoom);

        // ── Cluster convex hulls ──
        const hullGroup = g.append('g').attr('class', 'hulls');

        // ── Edges ──
        const edgeGroup = g.append('g').attr('class', 'edges');
        const links = edgeGroup
            .selectAll<SVGLineElement, GraphEdge>('line')
            .data(data.edges)
            .join('line')
            .attr('stroke', '#ddd')
            .attr('stroke-width', (d) => Math.max(0.5, d.weight * 2))
            .attr('stroke-opacity', 0.6);

        // ── Nodes ──
        const nodeGroup = g.append('g').attr('class', 'nodes');
        const nodes = nodeGroup
            .selectAll<SVGCircleElement, GraphNode>('circle')
            .data(data.nodes)
            .join('circle')
            .attr('r', (d) => sizeScale(d.citations_count))
            .attr('fill', (d) => clusterColorMap(d.cluster_id))
            .attr('stroke', '#fff')
            .attr('stroke-width', 1.5)
            .style('cursor', 'pointer');

        // ── Tooltip ──
        const tooltip = d3
            .select('body')
            .append('div')
            .attr('class', 'graph-tooltip')
            .style('position', 'absolute')
            .style('pointer-events', 'none')
            .style('background', 'rgba(0,0,0,0.8)')
            .style('color', '#fff')
            .style('padding', '6px 10px')
            .style('border-radius', '4px')
            .style('font-size', '12px')
            .style('max-width', '280px')
            .style('z-index', '10000')
            .style('opacity', 0);

        nodes
            .on('mouseover', (_event, d) => {
                tooltip
                    .html(
                        `<strong>${d.title}</strong><br/>` +
                        `${d.year ?? '—'} · 引用: ${d.citations_count}` +
                        (d.cluster_name ? `<br/>聚类: ${d.cluster_name}` : ''),
                    )
                    .style('opacity', 1);
            })
            .on('mousemove', (event) => {
                tooltip
                    .style('left', event.pageX + 12 + 'px')
                    .style('top', event.pageY - 10 + 'px');
            })
            .on('mouseout', () => {
                tooltip.style('opacity', 0);
            })
            .on('click', (_event, d) => {
                selectNode(selectedNodeId === d.id ? null : d.id);
            });

        // ── Drag ──
        const drag = d3
            .drag<SVGCircleElement, GraphNode>()
            .on('start', (event, d) => {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on('drag', (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on('end', (event, d) => {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            });
        nodes.call(drag);

        // ── Simulation ──
        const simulation = d3
            .forceSimulation<GraphNode>(data.nodes)
            .force(
                'link',
                d3
                    .forceLink<GraphNode, GraphEdge>(data.edges)
                    .id((d) => d.id)
                    .distance(80),
            )
            .force('charge', d3.forceManyBody().strength(-200))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide<GraphNode>().radius((d) => sizeScale(d.citations_count) + 2))
            .on('tick', () => {
                links
                    .attr('x1', (d) => (d.source as GraphNode).x ?? 0)
                    .attr('y1', (d) => (d.source as GraphNode).y ?? 0)
                    .attr('x2', (d) => (d.target as GraphNode).x ?? 0)
                    .attr('y2', (d) => (d.target as GraphNode).y ?? 0);

                nodes.attr('cx', (d) => d.x ?? 0).attr('cy', (d) => d.y ?? 0);

                // Update cluster hulls
                updateHulls();
            });

        simulationRef.current = simulation;

        function updateHulls() {
            hullGroup.selectAll('path').remove();
            const clusterGroups = d3.group(data.nodes, (d) => d.cluster_id);
            clusterGroups.forEach((clusterNodes, clusterId) => {
                if (!clusterId || clusterNodes.length < 3) return;
                const points: [number, number][] = clusterNodes.map((d) => [d.x ?? 0, d.y ?? 0]);
                const hull = d3.polygonHull(points);
                if (!hull) return;
                hullGroup
                    .append('path')
                    .datum(hull)
                    .attr('d', (d) => `M${d.join('L')}Z`)
                    .attr('fill', clusterColorMap(clusterId))
                    .attr('fill-opacity', 0.08)
                    .attr('stroke', clusterColorMap(clusterId))
                    .attr('stroke-opacity', 0.2)
                    .attr('stroke-width', 1);
            });
        }

        return () => {
            simulation.stop();
            tooltip.remove();
        };
    }, [data, width, height, clusterColorMap, selectNode]);

    // ── Reactive highlight: cluster filter ──
    useEffect(() => {
        if (!svgRef.current) return;
        const svg = d3.select(svgRef.current);
        const showAll = highlightedClusters.size === 0;

        svg.selectAll<SVGCircleElement, GraphNode>('circle').attr('opacity', (d) =>
            showAll || highlightedClusters.has(d.cluster_id ?? '') ? 1 : 0.15,
        );
        svg.selectAll<SVGLineElement, GraphEdge>('line').attr('opacity', (d) => {
            if (showAll) return 0.6;
            const src = (d.source as GraphNode).cluster_id ?? '';
            const tgt = (d.target as GraphNode).cluster_id ?? '';
            return highlightedClusters.has(src) || highlightedClusters.has(tgt) ? 0.6 : 0.05;
        });
    }, [highlightedClusters]);

    // ── Reactive highlight: search query ──
    useEffect(() => {
        if (!svgRef.current) return;
        const svg = d3.select(svgRef.current);
        const q = searchQuery.toLowerCase().trim();
        if (!q) {
            svg.selectAll<SVGCircleElement, GraphNode>('circle')
                .attr('stroke', '#fff')
                .attr('stroke-width', 1.5);
            return;
        }
        svg.selectAll<SVGCircleElement, GraphNode>('circle')
            .attr('stroke', (d) => (d.title.toLowerCase().includes(q) ? '#faad14' : '#fff'))
            .attr('stroke-width', (d) => (d.title.toLowerCase().includes(q) ? 3 : 1.5));
    }, [searchQuery]);

    // ── Reactive highlight: selected node ──
    useEffect(() => {
        if (!svgRef.current) return;
        const svg = d3.select(svgRef.current);
        svg.selectAll<SVGCircleElement, GraphNode>('circle')
            .attr('stroke', (d) => (d.id === selectedNodeId ? '#faad14' : '#fff'))
            .attr('stroke-width', (d) => (d.id === selectedNodeId ? 3 : 1.5));
    }, [selectedNodeId]);

    if (!data.nodes.length) {
        return <Text type="secondary">暂无知识图谱数据</Text>;
    }

    return (
        <svg
            ref={svgRef}
            width={width}
            height={height}
            style={{ background: '#fafafa', borderRadius: 8, display: 'block' }}
        />
    );
}
