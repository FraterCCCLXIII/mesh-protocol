/**
 * Main Layout with Navigation
 */
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/contexts/AuthContext';
import { 
  Home, Search, Bell, Mail, Users, BookOpen, 
  Settings, LogOut, Menu, X,
  Plus
} from 'lucide-react';
import { useState } from 'react';

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery)}`);
    }
  }

  function handleLogout() {
    logout();
    navigate('/');
  }

  const navItems = [
    { path: '/', icon: Home, label: 'Home' },
    { path: '/search', icon: Search, label: 'Search' },
    { path: '/groups', icon: Users, label: 'Groups' },
    { path: '/publications', icon: BookOpen, label: 'Publications' },
  ];

  const authNavItems = [
    { path: '/notifications', icon: Bell, label: 'Notifications' },
    { path: '/messages', icon: Mail, label: 'Messages' },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile Header */}
      <header className="md:hidden fixed top-0 left-0 right-0 h-14 border-b bg-background/95 backdrop-blur z-50 flex items-center px-4">
        <Link to="/" className="shrink-0 text-lg font-bold">
          Holons
        </Link>
        
        <form onSubmit={handleSearch} className="flex-1 mx-4">
          <Input
            placeholder="Search..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="h-9"
          />
        </form>

        <button onClick={() => setMobileMenuOpen(true)}>
          <Menu className="h-6 w-6" />
        </button>
      </header>

      {/* Mobile Menu Overlay */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-0 z-50">
          <div 
            className="absolute inset-0 bg-black/50" 
            onClick={() => setMobileMenuOpen(false)} 
          />
          <div className="absolute right-0 top-0 h-full w-72 bg-background border-l p-4">
            <div className="flex justify-end mb-4">
              <button onClick={() => setMobileMenuOpen(false)}>
                <X className="h-6 w-6" />
              </button>
            </div>
            
            <nav className="space-y-1">
              {navItems.map(item => (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg transition ${
                    location.pathname === item.path 
                      ? 'bg-primary/10 text-primary font-semibold' 
                      : 'hover:bg-muted'
                  }`}
                >
                  <item.icon className="h-5 w-5" />
                  <span>{item.label}</span>
                </Link>
              ))}
              
              {isAuthenticated && authNavItems.map(item => (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg transition ${
                    location.pathname === item.path 
                      ? 'bg-primary/10 text-primary font-semibold' 
                      : 'hover:bg-muted'
                  }`}
                >
                  <item.icon className="h-5 w-5" />
                  <span>{item.label}</span>
                </Link>
              ))}

              {isAuthenticated && (
                <>
                  <Link
                    to="/settings"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-muted"
                  >
                    <Settings className="h-5 w-5" />
                    <span>Settings</span>
                  </Link>
                  <button
                    onClick={() => { handleLogout(); setMobileMenuOpen(false); }}
                    className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-muted w-full text-left text-destructive"
                  >
                    <LogOut className="h-5 w-5" />
                    <span>Log out</span>
                  </button>
                </>
              )}

              {!isAuthenticated && (
                <Link
                  to="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-3 rounded-lg bg-foreground text-background hover:bg-foreground/90"
                >
                  Sign In
                </Link>
              )}
            </nav>
          </div>
        </div>
      )}

      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 h-16 border-t bg-background z-40 flex items-center justify-around px-4">
        {navItems.slice(0, 4).map(item => (
          <Link
            key={item.path}
            to={item.path}
            className={`flex flex-col items-center gap-1 px-3 py-2 ${
              location.pathname === item.path ? 'text-primary' : 'text-muted-foreground'
            }`}
          >
            <item.icon className="h-5 w-5" />
            <span className="text-xs">{item.label}</span>
          </Link>
        ))}
        {isAuthenticated && (
          <Link
            to="/notifications"
            className={`flex flex-col items-center gap-1 px-3 py-2 ${
              location.pathname === '/notifications' ? 'text-primary' : 'text-muted-foreground'
            }`}
          >
            <Bell className="h-5 w-5" />
            <span className="text-xs">Alerts</span>
          </Link>
        )}
      </nav>

      {/* Main Content — desktop nav lives in <Sidebar /> inside each page */}
      <main className="pt-14 md:pt-0 pb-20 md:pb-0">
        <Outlet />
      </main>

      {/* FAB for mobile compose */}
      {isAuthenticated && (
        <Link
          to="/write"
          className="md:hidden fixed bottom-20 right-4 h-14 w-14 rounded-full bg-foreground text-background hover:bg-foreground/90 flex items-center justify-center shadow-lg z-40"
        >
          <Plus className="h-6 w-6" />
        </Link>
      )}
    </div>
  );
}
