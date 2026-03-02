import { NavLink } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import ProjectSwitcher from "./ProjectSwitcher";
import {
  LayoutDashboard,
  Shield,
  Brain,
  History,
  Settings2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const navItems: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/policies", label: "Policies", icon: Shield },
  { to: "/intelligence", label: "Codebase Intelligence", icon: Brain },
  { to: "/scans", label: "Scan History", icon: History },
  { to: "/settings", label: "Settings", icon: Settings2 },
];

interface Props {
  onNavigate?: () => void;
}

export default function Sidebar({ onNavigate }: Props) {
  const { user } = useAuth();

  return (
    <aside className="flex h-full w-64 flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex items-center gap-2 px-4 py-5">
        <Shield className="h-6 w-6 text-sidebar-primary" />
        <span className="text-lg font-bold">ForgeLine</span>
      </div>
      <div className="px-3">
        <ProjectSwitcher />
      </div>
      <Separator className="my-3 bg-sidebar-border" />
      <nav className="flex-1 space-y-1 px-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-sidebar-primary text-sidebar-primary-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              }`
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <Separator className="bg-sidebar-border" />
      <div className="flex items-center gap-3 px-4 py-3">
        <Avatar className="h-8 w-8">
          <AvatarFallback className="bg-sidebar-accent text-sidebar-accent-foreground text-xs">
            {user?.full_name?.charAt(0)?.toUpperCase() ?? "U"}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 truncate">
          <p className="truncate text-sm font-medium">
            {user?.full_name ?? "User"}
          </p>
          <p className="truncate text-xs text-sidebar-foreground/60">
            {user?.email ?? ""}
          </p>
        </div>
      </div>
    </aside>
  );
}
