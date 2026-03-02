import { useLocation, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Menu, LogOut, Settings2 } from "lucide-react";
import { Fragment } from "react";

const routeLabels: Record<string, string> = {
  "/": "Dashboard",
  "/policies": "Policies",
  "/intelligence": "Codebase Intelligence",
  "/scans": "Scan History",
  "/settings": "Settings",
};

interface Props {
  onMobileMenuToggle: () => void;
}

export default function Header({ onMobileMenuToggle }: Props) {
  const { user, logout } = useAuth();
  const location = useLocation();

  const segments = location.pathname.split("/").filter(Boolean);
  const crumbs: { label: string; path: string }[] = [
    { label: "Dashboard", path: "/" },
  ];

  if (segments.length > 0) {
    let accumulated = "";
    for (const seg of segments) {
      accumulated += `/${seg}`;
      const label = routeLabels[accumulated] ?? seg;
      crumbs.push({ label, path: accumulated });
    }
  }

  return (
    <header>
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={onMobileMenuToggle}
          >
            <Menu className="h-5 w-5" />
          </Button>
          <Breadcrumb>
            <BreadcrumbList>
              {crumbs.map((crumb, i) => (
                <Fragment key={crumb.path}>
                  {i > 0 && <BreadcrumbSeparator />}
                  <BreadcrumbItem>
                    {i === crumbs.length - 1 ? (
                      <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                    ) : (
                      <BreadcrumbLink asChild>
                        <Link to={crumb.path}>{crumb.label}</Link>
                      </BreadcrumbLink>
                    )}
                  </BreadcrumbItem>
                </Fragment>
              ))}
            </BreadcrumbList>
          </Breadcrumb>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="gap-2">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="text-xs">
                  {user?.full_name?.charAt(0)?.toUpperCase() ?? "U"}
                </AvatarFallback>
              </Avatar>
              <span className="hidden text-sm sm:inline">
                {user?.full_name ?? "User"}
              </span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link to="/settings">
                <Settings2 className="mr-2 h-4 w-4" />
                Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout}>
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <Separator />
    </header>
  );
}
