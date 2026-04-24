import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { HomePage } from './pages/Home';
import { ProfilePage } from './pages/Profile';
import { GroupsPage } from './pages/Groups';
import { PublicationsPage } from './pages/Publications';
import { NewPublicationPage } from './pages/NewPublication';
import { PublicationDetailPage } from './pages/PublicationDetail';
import { WritePage } from './pages/Write';
import { ArticlePage } from './pages/Article';
import { PostDetailPage } from './pages/PostDetail';

function App() {
  return (
    <BrowserRouter>
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
    </BrowserRouter>
  );
}

export default App;
