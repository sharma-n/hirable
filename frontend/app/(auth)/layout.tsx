import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AuthProvider } from "@/lib/auth";

export default async function AuthLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  if (cookieStore.has("hirable_session")) {
    redirect("/chat");
  }
  return (
    <AuthProvider>
      <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
        {children}
      </div>
    </AuthProvider>
  );
}
