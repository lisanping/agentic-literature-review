import { Routes, Route } from 'react-router-dom';
import ErrorBoundary from '@/components/Common/ErrorBoundary';
import AppLayout from '@/components/Layout/AppLayout';
import HomePage from '@/pages/HomePage';
import ProjectPage from '@/pages/ProjectPage';
import NotFoundPage from '@/pages/NotFoundPage';

export default function App() {
    return (
        <ErrorBoundary>
            <Routes>
                {/* 带布局的路由 */}
                <Route element={<AppLayout />}>
                    <Route path="/" element={<HomePage />} />
                    <Route path="/projects/:projectId" element={<ProjectPage />} />
                </Route>

                {/* 无布局的路由 */}
                <Route path="*" element={<NotFoundPage />} />
            </Routes>
        </ErrorBoundary>
    );
}
