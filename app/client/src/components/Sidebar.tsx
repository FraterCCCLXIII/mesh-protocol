import { Link, useLocation } from "react-router-dom";
import { 
  Home, 
  User, 
  Users, 
  Bell, 
  Settings, 
  LogOut,
  PenSquare,
  FileText,
  Search,
  Mail,
} from "lucide-react";
import { Button } from "./ui/button";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { getStoredUser, clearAuth } from "../lib/mesh";

const navItems = [
  { href: "/", icon: Home, label: "Home" },
  { href: "/search", icon: Search, label: "Search" },
  { href: "/profile", icon: User, label: "Profile" },
  { href: "/groups", icon: Users, label: "Groups" },
  { href: "/publications", icon: FileText, label: "Publications" },
  { href: "/notifications", icon: Bell, label: "Notifications" },
  { href: "/messages", icon: Mail, label: "Messages" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

function isNavActive(href: string, pathname: string): boolean {
  if (href === "/profile") {
    return pathname === "/profile" || pathname.startsWith("/profile/");
  }
  if (href === "/messages") {
    return pathname === "/messages" || pathname.startsWith("/messages/");
  }
  return pathname === href;
}

export function Sidebar() {
  const location = useLocation();
  const user = getStoredUser();

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
    <aside className="hidden w-64 shrink-0 flex-col p-4 md:flex md:min-h-screen">
      <div className="flex min-h-0 flex-1 flex-col gap-4">
        {/* Logo */}
        <Link to="/" className="shrink-0 px-4 py-2">
          <span className="text-xl font-bold">Holons</span>
        </Link>

        {/* Navigation */}
        <nav className="shrink-0 space-y-1">
          {navItems.map((item) => {
            const isActive = isNavActive(item.href, location.pathname);
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

        {/* Post — link styled as button (same destination as mobile compose) */}
        <Button
          variant="invert"
          className="w-full shrink-0 rounded-full py-6 text-base font-bold"
          asChild
        >
          <Link to="/write">
            <PenSquare className="mr-2 h-5 w-5" />
            Post
          </Link>
        </Button>

        {/* User profile — bottom-aligned in column */}
        {user && (
          <div className="mt-auto border-t pt-4">
            <div className="flex items-center gap-3 rounded-full p-3 transition-colors hover:bg-muted">
              <Avatar>
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
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
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
