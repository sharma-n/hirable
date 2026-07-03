"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  Briefcase,
  Moon,
  Sun,
  FileText,
  Bookmark,
  BarChart2,
  ShieldCheck,
  LogOut,
  User,
} from "lucide-react";
import { toast } from "sonner";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/profile", label: "Profile", icon: User },
  { href: "/jobs", label: "Jobs", icon: Bookmark },
  { href: "/documents", label: "Documents", icon: FileText, disabled: true },
  { href: "/analytics", label: "Analytics", icon: BarChart2, disabled: true },
];

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label="Toggle theme"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
    >
      <Sun className="size-4 scale-100 rotate-0 transition-transform dark:scale-0 dark:-rotate-90" />
      <Moon className="absolute size-4 scale-0 rotate-90 transition-transform dark:scale-100 dark:rotate-0" />
    </Button>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    try {
      await logout();
      router.push("/login");
    } catch {
      toast.error("Logout failed");
    }
  }

  const initials = user?.email?.slice(0, 2).toUpperCase() ?? "??";

  return (
    <div className="flex min-h-screen flex-col">
      {/* Top nav */}
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex h-14 items-center px-4 gap-4">
          {/* Brand */}
          <Link href="/profile" className="flex items-center gap-2 shrink-0">
            <Briefcase className="size-5 text-primary" />
            <span className="font-bold tracking-tight text-sm">hirable</span>
          </Link>

          {/* Nav links */}
          <nav className="flex items-center gap-1 ml-2">
            {NAV_ITEMS.map(({ href, label, icon: Icon, disabled }) => (
              <Link
                key={href}
                href={disabled ? "#" : href}
                aria-disabled={disabled}
                tabIndex={disabled ? -1 : undefined}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  disabled
                    ? "text-muted-foreground/50 cursor-not-allowed pointer-events-none"
                    : pathname === href
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="size-3.5" />
                {label}
                {disabled && (
                  <span className="ml-1 hidden sm:inline text-[10px] text-muted-foreground/60">
                    soon
                  </span>
                )}
              </Link>
            ))}
            {user?.role === "admin" && (
              <Link
                href="/admin"
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  pathname === "/admin"
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <ShieldCheck className="size-3.5" />
                Admin
              </Link>
            )}
          </nav>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Right side */}
          <ThemeToggle />

          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" size="icon-sm" className="rounded-full" />
              }
            >
              <Avatar className="size-7">
                <AvatarFallback className="text-xs bg-primary/10 text-primary font-semibold">
                  {initials}
                </AvatarFallback>
              </Avatar>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuGroup>
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium truncate">{user?.email}</p>
                    <Badge variant="secondary" className="w-fit text-xs capitalize">
                      {user?.role}
                    </Badge>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive cursor-pointer"
                  onClick={handleLogout}
                >
                  <LogOut className="mr-2 size-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Page content */}
      <main className="flex flex-1 flex-col min-h-0">{children}</main>
    </div>
  );
}
