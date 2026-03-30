import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        port: 5173,
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/healthz': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/readyz': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
        },
    },
    build: {
        rollupOptions: {
            output: {
                manualChunks(id) {
                    if (id.includes('node_modules')) {
                        if (id.includes('react-dom') || id.includes('react-router')) return 'vendor';
                        if (id.includes('react-markdown') || id.includes('remark') || id.includes('mdast') || id.includes('micromark') || id.includes('unified') || id.includes('unist')) return 'markdown';
                        if (id.includes('antd') || id.includes('@ant-design') || id.includes('rc-')) return 'antd';
                    }
                },
            },
        },
        chunkSizeWarningLimit: 1000,
    },
});
