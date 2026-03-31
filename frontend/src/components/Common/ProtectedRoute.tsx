import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

interface ProtectedRouteProps {
    children: React.ReactNode;
}

/**
 * Route guard — redirects to /login if not authenticated.
 * Preserves the attempted URL for redirect after login.
 */
export default function ProtectedRoute({ children }: ProtectedRouteProps) {
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const location = useLocation();

    if (!isAuthenticated) {
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return <>{children}</>;
}
