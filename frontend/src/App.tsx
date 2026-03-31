import { useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import ErrorBoundary from '@/components/Common/ErrorBoundary';
import ProtectedRoute from '@/components/Common/ProtectedRoute';
import AppLayout from '@/components/Layout/AppLayout';
import HomePage from '@/pages/HomePage';
import ProjectPage from '@/pages/ProjectPage';
import LoginPage from '@/pages/LoginPage';
import SettingsPage from '@/pages/SettingsPage';
import NotFoundPage from '@/pages/NotFoundPage';
import { useAuthStore } from '@/stores/authStore';
import * as authApi from '@/api/auth';

export default function App() {
    const { isAuthenticated, setUser, setLoading, clearAuth } = useAuthStore();

    // Hydrate user info from token on mount
    useEffect(() => {
        if (!isAuthenticated) return;
        setLoading(true);
        authApi
            .getMe()
            .then((resp) => setUser(resp.data))
            .catch(() => clearAuth())
            .finally(() => setLoading(false));
    }, [isAuthenticated]);

    return (
        <ErrorBoundary>
            <Routes>
                {/* 公开页面 */}
                <Route path="/login" element={<LoginPage />} />

                {/* 需要认证的页面 */}
                <Route
                    element={
                        <ProtectedRoute>
                            <AppLayout />
                        </ProtectedRoute>
                    }
                >
                    <Route path="/" element={<HomePage />} />
                    <Route path="/projects/:projectId" element={<ProjectPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                </Route>

                {/* 404 */}
                <Route path="*" element={<NotFoundPage />} />
            </Routes>
        </ErrorBoundary>
    );
}
