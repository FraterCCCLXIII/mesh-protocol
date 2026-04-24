import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Suspense, lazy, Component, ReactNode, ErrorInfo } from 'react';

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
const HomePage = lazy(() => import('./pages/Home').then(m => ({ default: m.HomePage })));
const ProfilePage = lazy(() => import('./pages/Profile').then(m => ({ default: m.ProfilePage })));
const GroupsPage = lazy(() => import('./pages/Groups').then(m => ({ default: m.GroupsPage })));
const PublicationsPage = lazy(() => import('./pages/Publications').then(m => ({ default: m.PublicationsPage })));
const NewPublicationPage = lazy(() => import('./pages/NewPublication').then(m => ({ default: m.NewPublicationPage })));
const PublicationDetailPage = lazy(() => import('./pages/PublicationDetail').then(m => ({ default: m.PublicationDetailPage })));
const WritePage = lazy(() => import('./pages/Write').then(m => ({ default: m.WritePage })));
const ArticlePage = lazy(() => import('./pages/Article').then(m => ({ default: m.ArticlePage })));
const PostDetailPage = lazy(() => import('./pages/PostDetail').then(m => ({ default: m.PostDetailPage })));

function Loading() {
  return (
    <div style={{ padding: '40px', textAlign: 'center', fontFamily: 'sans-serif' }}>
      <p>Loading...</p>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/profile/:handle" element={<ProfilePage />} />
            <Route path="/groups" element={<GroupsPage />} />
            <Route path="/publications" element={<PublicationsPage />} />
            <Route path="/publications/new" element={<NewPublicationPage />} />
            <Route path="/publications/:id" element={<PublicationDetailPage />} />
            <Route path="/write" element={<WritePage />} />
            <Route path="/article/:id" element={<ArticlePage />} />
            <Route path="/post/:id" element={<PostDetailPage />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
