import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

/**
 * useD3 — manages a D3.js + React SVG ref lifecycle.
 *
 * @param renderFn Called when the SVG element is ready. Receives the D3 Selection.
 *                 Return an optional cleanup function.
 * @param deps     React dependency array — re-runs renderFn when deps change.
 */
export function useD3(
    renderFn: (svg: d3.Selection<SVGSVGElement, unknown, null, undefined>) => (() => void) | void,
    deps: React.DependencyList,
) {
    const svgRef = useRef<SVGSVGElement>(null);
    const cleanupRef = useRef<(() => void) | void>(undefined);

    useEffect(() => {
        if (!svgRef.current) return;

        // Clean up previous render
        if (cleanupRef.current) {
            cleanupRef.current();
        }

        const svg = d3.select(svgRef.current);
        cleanupRef.current = renderFn(svg);

        return () => {
            if (cleanupRef.current) {
                cleanupRef.current();
                cleanupRef.current = undefined;
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, deps);

    return svgRef;
}

/**
 * Export SVG element as PNG data URL.
 */
export function svgToPng(svgEl: SVGSVGElement, scale = 2): Promise<string> {
    return new Promise((resolve, reject) => {
        const svgData = new XMLSerializer().serializeToString(svgEl);
        const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
        const url = URL.createObjectURL(svgBlob);

        const canvas = document.createElement('canvas');
        const rect = svgEl.getBoundingClientRect();
        canvas.width = rect.width * scale;
        canvas.height = rect.height * scale;

        const ctx = canvas.getContext('2d');
        if (!ctx) {
            reject(new Error('Canvas 2D context unavailable'));
            return;
        }

        const img = new Image();
        img.onload = () => {
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(url);
            resolve(canvas.toDataURL('image/png'));
        };
        img.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error('SVG to PNG conversion failed'));
        };
        img.src = url;
    });
}
