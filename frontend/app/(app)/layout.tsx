import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AuthProvider } from "@/lib/auth";
import { AppShell } from "@/components/app-shell";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  if (!cookieStore.has("hirable_session")) {
    redirect("/login");
  }
  return (
    <AuthProvider>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
