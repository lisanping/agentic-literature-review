/** SVG / PNG export utilities — v0.4 */

/**
 * Download SVG element as an .svg file.
 */
export function downloadSvg(svgEl: SVGSVGElement, filename = 'chart.svg') {
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svgEl);
    const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    triggerDownload(blob, filename);
}

/**
 * Download SVG element as a .png file (renders via canvas).
 */
export async function downloadPng(svgEl: SVGSVGElement, filename = 'chart.png', scale = 2) {
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svgEl);
    const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);

    const canvas = document.createElement('canvas');
    const rect = svgEl.getBoundingClientRect();
    canvas.width = rect.width * scale;
    canvas.height = rect.height * scale;

    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas 2D context unavailable');

    return new Promise<void>((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(url);
            canvas.toBlob((blob) => {
                if (blob) {
                    triggerDownload(blob, filename);
                    resolve();
                } else {
                    reject(new Error('PNG conversion failed'));
                }
            }, 'image/png');
        };
        img.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error('SVG to PNG conversion failed'));
        };
        img.src = url;
    });
}

function triggerDownload(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
