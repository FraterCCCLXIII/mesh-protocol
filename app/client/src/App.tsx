import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Suspense, lazy, Component, type ReactNode, type ErrorInfo } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';

// Error boundary for catching component errors
class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('App Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', color: 'red' }}>
          <h1>Something went wrong</h1>
          <pre>{this.state.error?.message}</pre>
          <pre>{this.state.error?.stack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

// Lazy load pages
const HomePage = lazy(() => import('./pages/Home'));
const ProfilePage = lazy(() => import('./pages/Profile'));
const GroupsPage = lazy(() => import('./pages/Groups'));
const GroupDetailPage = lazy(() => import('./pages/GroupDetail'));
const PublicationsPage = lazy(() => import('./pages/Publications'));
const NewPublicationPage = lazy(() => import('./pages/NewPublication'));
const PublicationDetailPage = lazy(() => import('./pages/PublicationDetail'));
const WritePage = lazy(() => import('./pages/Write'));
const ArticlePage = lazy(() => import('./pages/Article'));
const PostDetailPage = lazy(() => import('./pages/PostDetail'));
const MessagesPage = lazy(() => import('./pages/Messages'));
const NotificationsPage = lazy(() => import('./pages/Notifications'));
const SearchPage = lazy(() => import('./pages/Search'));
const SettingsPage = lazy(() => import('./pages/Settings'));
const FriendRequestsPage = lazy(() => import('./pages/FriendRequests'));
const LoginPage = lazy(() => import('./pages/Login'));

function Loading() {
  return (
    <div style={{ padding: '40px', textAlign: 'center', fontFamily: 'sans-serif' }}>
      <p>Loading...</p>
    </div>
  );
}

// Protected route wrapper
function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) {
    return <Loading />;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      
      {/* Routes with Layout */}
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/profile/:handle" element={<ProfilePage />} />
        <Route path="/groups" element={<GroupsPage />} />
        <Route path="/groups/:groupId" element={<GroupDetailPage />} />
        <Route path="/publications" element={<PublicationsPage />} />
        <Route path="/publications/:id" element={<PublicationDetailPage />} />
        <Route path="/article/:id" element={<ArticlePage />} />
        <Route path="/post/:id" element={<PostDetailPage />} />
        <Route path="/search" element={<SearchPage />} />
        
        {/* Protected routes */}
        <Route path="/messages" element={<ProtectedRoute><MessagesPage /></ProtectedRoute>} />
        <Route path="/messages/:participantId" element={<ProtectedRoute><MessagesPage /></ProtectedRoute>} />
        <Route path="/notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />
        <Route path="/friend-requests" element={<ProtectedRoute><FriendRequestsPage /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        <Route path="/publications/new" element={<ProtectedRoute><NewPublicationPage /></ProtectedRoute>} />
        <Route path="/write" element={<ProtectedRoute><WritePage /></ProtectedRoute>} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<Loading />}>
            <AppRoutes />
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
