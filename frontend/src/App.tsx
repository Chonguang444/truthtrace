import { BrowserRouter, Routes, Route, Link, useLocation, useNavigate } from "react-router-dom";
import { Suspense, lazy } from "react";
import { Home } from "./pages/Home";
import { Search } from "./pages/Search";
import { EventDetail } from "./pages/EventDetail";
import { RumorSquare } from "./pages/RumorSquare";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { Admin } from "./pages/Admin";
// Lazy-loaded heavy pages – only fetched when navigated to
const TraceReport = lazy(() => import("./pages/TraceReport").then(m => ({ default: m.TraceReport })));
const LiteracyAcademy = lazy(() => import("./pages/LiteracyAcademy"));
const SituationalAwareness = lazy(() => import("./pages/SituationalAwareness"));
const CommunityHub = lazy(() => import("./pages/CommunityHub"));
const DebunkStudio = lazy(() => import("./pages/DebunkStudio"));
const DeveloperPortal = lazy(() => import("./pages/DeveloperPortal"));
const QuickCheck = lazy(() => import("./pages/QuickCheck"));
import { ErrorBoundary } from "./components/ErrorBoundary";
import { useTheme } from "./hooks/useTheme";
import { LanguageSwitcher } from "./components/LanguageSwitcher";
import { NotificationBell } from "./components/NotificationBell";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import {
  Search as SearchIcon, Shield, Activity, Menu, Sun, Moon, Monitor,
  User, LogOut, Heart, Settings, X, ChevronDown, BookOpen, TrendingUp, Users, PenTool, Code, Zap,
} from "lucide-react";
import { useState, useRef, useEffect } from "react";

// ---------------------------------------------------------------------------
// Theme Toggle
// ---------------------------------------------------------------------------

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  const icon =
    theme === "dark" ? (
      <Moon className="h-4 w-4" />
    ) : theme === "light" ? (
      <Sun className="h-4 w-4" />
    ) : (
      <Monitor className="h-4 w-4" />
    );

  const label =
    theme === "dark" ? "深色模式" : theme === "light" ? "浅色模式" : "跟随系统";

  return (
    <button
      onClick={toggleTheme}
      className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
      title={`当前: ${label} — 点击切换`}
      aria-label="切换主题"
    >
      {icon}
    </button>
  );
}

// ---------------------------------------------------------------------------
// User Menu Dropdown (F6)
// ---------------------------------------------------------------------------

function UserMenu() {
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  if (isLoading) {
    return <div className="h-8 w-8 rounded-full bg-muted animate-pulse" />;
  }

  if (!isAuthenticated) {
    return (
      <Link
        to="/login"
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        <User className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">登录</span>
      </Link>
    );
  }

  const initials = (user?.display_name || user?.username || "U").slice(0, 2).toUpperCase();

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 p-1.5 rounded-lg hover:bg-accent transition-colors"
      >
        <div className="h-7 w-7 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center">
          {initials}
        </div>
        <span className="hidden sm:inline text-sm font-medium max-w-[100px] truncate">
          {user?.display_name || user?.username}
        </span>
        <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-2 w-56 rounded-xl border bg-card shadow-lg z-50 overflow-hidden">
            {/* User info */}
            <div className="px-4 py-3 border-b">
              <p className="text-sm font-semibold truncate">{user?.display_name || user?.username}</p>
              <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
              <span className="inline-block mt-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs capitalize">
                {user?.role === "admin" ? "管理员" : user?.role === "analyst" ? "分析师" : "用户"}
              </span>
            </div>

            <div className="p-1">
              <button
                onClick={() => { setOpen(false); navigate("/admin"); }}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm hover:bg-accent transition-colors"
              >
                <Settings className="h-4 w-4" />
                管理后台
              </button>
              <button
                onClick={() => { setOpen(false); }}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm hover:bg-accent transition-colors"
              >
                <Heart className="h-4 w-4" />
                我的收藏
              </button>
            </div>

            <div className="border-t p-1">
              <button
                onClick={() => { setOpen(false); logout(); navigate("/"); }}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
              >
                <LogOut className="h-4 w-4" />
                退出登录
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// NavBar
// ---------------------------------------------------------------------------

function NavBar() {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  const links = [
    { to: "/", label: "首页", icon: Activity },
    { to: "/search", label: "搜索", icon: SearchIcon },
    { to: "/quick", label: "快速检测", icon: Zap },
    { to: "/rumors", label: "辟谣广场", icon: Shield },
    { to: "/academy", label: "信息素养", icon: BookOpen },
    { to: "/situational", label: "态势感知", icon: TrendingUp },
    { to: "/community", label: "协作众包", icon: Users },
  ];

  const moreLinks = [
    { to: "/studio", label: "辟谣工坊", icon: PenTool },
    { to: "/developer", label: "API平台", icon: Code },
  ];

  return (
    <nav className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <Link to="/" className="flex items-center gap-2 font-bold text-xl">
          <Shield className="h-6 w-6 text-primary" />
          <span>TruthTrace</span>
          <span className="text-xs text-muted-foreground font-normal hidden sm:inline">
            平浪散暴
          </span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-1">
          {links.map((link) => {
            const active = location.pathname === link.to;
            return (
              <Link
                key={link.to}
                to={link.to}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                }`}
              >
                <link.icon className="h-4 w-4" />
                {link.label}
              </Link>
            );
          })}
          {/* More links — smaller */}
          <div className="ml-1 pl-1 border-l flex items-center gap-1">
            {moreLinks.map((link) => {
              const active = location.pathname === link.to;
              return (
                <Link key={link.to} to={link.to}
                  className={`flex items-center gap-1 px-2 py-2 rounded-md text-xs font-medium transition-colors ${
                    active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent"
                  }`}>
                  <link.icon className="h-3.5 w-3.5" />
                  <span className="hidden lg:inline">{link.label}</span>
                </Link>
              );
            })}
          </div>
          <div className="ml-2 pl-2 border-l flex items-center gap-1">
            <LanguageSwitcher />
            <NotificationBell />
            <ThemeToggle />
            <UserMenu />
          </div>
        </div>

        {/* Mobile */}
        <div className="flex items-center gap-1 md:hidden">
          <LanguageSwitcher />
          <NotificationBell />
          <ThemeToggle />
          <UserMenu />
          <button className="p-2" onClick={() => setMenuOpen(!menuOpen)}>
            <Menu className="h-5 w-5" />
          </button>
        </div>
      </div>

      {menuOpen && (
        <div className="md:hidden border-t bg-background p-4 space-y-2">
          {links.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              onClick={() => setMenuOpen(false)}
              className="flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium hover:bg-accent"
            >
              <link.icon className="h-4 w-4" />
              {link.label}
            </Link>
          ))}
          <div className="border-t pt-2 mt-2">
            {moreLinks.map((link) => (
              <Link key={link.to} to={link.to} onClick={() => setMenuOpen(false)}
                className="flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium hover:bg-accent">
                <link.icon className="h-4 w-4" />{link.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}

// ---------------------------------------------------------------------------
// App Root
// ---------------------------------------------------------------------------

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="min-h-screen flex flex-col bg-background text-foreground transition-colors">
          <NavBar />
          <ErrorBoundary>
            <main className="flex-1">
              <Suspense fallback={<div className="flex items-center justify-center py-20"><div className="h-8 w-8 border-4 border-primary/30 border-t-primary rounded-full animate-spin" /></div>}>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/search" element={<Search />} />
                  <Route path="/events/:eventId" element={<EventDetail />} />
                  <Route path="/events/:eventId/report" element={<TraceReport />} />
                  <Route path="/rumors" element={<RumorSquare />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/register" element={<Register />} />
                  <Route path="/admin" element={<Admin />} />
                  <Route path="/academy" element={<LiteracyAcademy />} />
                  <Route path="/situational" element={<SituationalAwareness />} />
                  <Route path="/community" element={<CommunityHub />} />
                  <Route path="/studio" element={<DebunkStudio />} />
                  <Route path="/developer" element={<DeveloperPortal />} />
                <Route path="/quick" element={<QuickCheck />} />
                </Routes>
              </Suspense>
            </main>
          </ErrorBoundary>
          <footer className="border-t py-6 text-center text-sm text-muted-foreground">
            <p>TruthTrace — 平浪散暴平台 | 追溯真相，破除谣言</p>
          </footer>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
