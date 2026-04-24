import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { 
  Home, 
  User, 
  Users, 
  Bell, 
  Settings, 
  LogOut,
  PenSquare,
  FileText
} from "lucide-react";
import { Button } from "./ui/button";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { getStoredUser, clearAuth } from "../lib/mesh";
import { ComposeDialog } from "./ComposeDialog";

const navItems = [
  { href: "/", icon: Home, label: "Home" },
  { href: "/profile", icon: User, label: "Profile" },
  { href: "/groups", icon: Users, label: "Groups" },
  { href: "/publications", icon: FileText, label: "Publications" },
  { href: "/notifications", icon: Bell, label: "Notifications" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const location = useLocation();
  const user = getStoredUser();
  const [composeOpen, setComposeOpen] = useState(false);

  const handleLogout = () => {
    clearAuth();
    window.location.reload();
  };

  const initials = user?.profile?.name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";

  return (
    <aside className="w-64 p-4 hidden md:block">
      <div className="sticky top-4 space-y-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 px-4 py-2">
          <div className="w-8 h-8 rounded-full bg-foreground flex items-center justify-center">
            <span className="text-background font-bold text-sm">M</span>
          </div>
          <span className="text-xl font-bold">MESH</span>
        </Link>

        {/* Navigation */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.href}
                to={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-full transition-colors ${
                  isActive
                    ? "font-bold bg-muted"
                    : "hover:bg-muted"
                }`}
              >
                <item.icon className="w-6 h-6" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Post Button */}
        <Button 
          className="w-full rounded-full py-6 text-base font-bold"
          onClick={() => setComposeOpen(true)}
        >
          <PenSquare className="w-5 h-5 mr-2" />
          Post
        </Button>

        {/* User Profile */}
        {user && (
          <div className="mt-auto pt-4 border-t">
            <div className="flex items-center gap-3 p-3 rounded-full hover:bg-muted transition-colors">
              <Avatar>
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="font-semibold truncate">{user.profile?.name || "User"}</p>
                <p className="text-sm text-muted-foreground truncate">
                  @{user.handle || user.id?.slice(4, 12)}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleLogout}
                title="Log out"
              >
                <LogOut className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </div>

      <ComposeDialog open={composeOpen} onOpenChange={setComposeOpen} />
    </aside>
  );
}
