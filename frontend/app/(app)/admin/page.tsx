"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { toast } from "sonner";
import { Loader2, RefreshCw, Trash2, Ban, CheckCircle, KeyRound } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  apiDeleteUser,
  apiDisableUser,
  apiEnableUser,
  apiListUsers,
  apiResetPassword,
  type User,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [resetPasswords, setResetPasswords] = useState<Record<string, string>>({});

  async function fetchUsers() {
    setLoading(true);
    try {
      setUsers(await apiListUsers());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (currentUser && currentUser.role !== "admin") {
      router.replace("/chat");
      return;
    }
    fetchUsers();
  }, [currentUser, router]);

  async function handleDelete(userId: string) {
    try {
      await apiDeleteUser(userId);
      toast.success("User deleted");
      setUsers((u) => u.filter((x) => x.id !== userId));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function handleDisable(userId: string) {
    try {
      await apiDisableUser(userId);
      toast.success("User disabled");
      setUsers((u) =>
        u.map((x) => (x.id === userId ? { ...x, is_active: false } : x)),
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Disable failed");
    }
  }

  async function handleEnable(userId: string) {
    try {
      await apiEnableUser(userId);
      toast.success("User enabled");
      setUsers((u) =>
        u.map((x) => (x.id === userId ? { ...x, is_active: true } : x)),
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Enable failed");
    }
  }

  async function handleResetPassword(userId: string) {
    const pw = resetPasswords[userId] ?? "";
    if (pw.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    try {
      await apiResetPassword(userId, pw);
      toast.success("Password reset and sessions invalidated");
      setResetPasswords((prev) => ({ ...prev, [userId]: "" }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Reset failed");
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Admin Console</h1>
          <p className="text-muted-foreground text-sm">Manage users and access</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchUsers} disabled={loading}>
          <RefreshCw className={`size-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Joined</TableHead>
                <TableHead className="w-72">Reset password</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => {
                const isSelf = u.id === currentUser?.id;
                return (
                  <TableRow key={u.id} className={!u.is_active ? "opacity-60" : undefined}>
                    <TableCell className="font-medium truncate max-w-[180px]">
                      {u.email}
                      {isSelf && (
                        <Badge variant="outline" className="ml-2 text-xs">
                          you
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={u.role === "admin" ? "default" : "secondary"}
                        className="capitalize"
                      >
                        {u.role}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={u.is_active ? "default" : "destructive"}
                        className="capitalize"
                      >
                        {u.is_active ? "active" : "disabled"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {format(new Date(u.created_at), "MMM d, yyyy")}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2 items-center">
                        <Input
                          type="password"
                          placeholder="New password…"
                          className="h-7 text-xs"
                          value={resetPasswords[u.id] ?? ""}
                          onChange={(e) =>
                            setResetPasswords((prev) => ({
                              ...prev,
                              [u.id]: e.target.value,
                            }))
                          }
                        />
                        <Button
                          size="icon-sm"
                          variant="outline"
                          onClick={() => handleResetPassword(u.id)}
                          title="Reset password"
                        >
                          <KeyRound className="size-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {/* Disable / Enable */}
                        {!isSelf && (
                          u.is_active ? (
                            <AlertDialog>
                              <AlertDialogTrigger
                                render={<Button size="icon-sm" variant="ghost" title="Disable user" />}
                              >
                                <Ban className="size-3.5" />
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Disable user?</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    {u.email} will be signed out and unable to log in.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => handleDisable(u.id)}>
                                    Disable
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          ) : (
                            <Button
                              size="icon-sm"
                              variant="ghost"
                              onClick={() => handleEnable(u.id)}
                              title="Enable user"
                            >
                              <CheckCircle className="size-3.5 text-green-600" />
                            </Button>
                          )
                        )}

                        {/* Delete */}
                        {!isSelf && (
                          <AlertDialog>
                            <AlertDialogTrigger
                              render={
                                <Button
                                  size="icon-sm"
                                  variant="ghost"
                                  className="text-destructive hover:text-destructive"
                                  title="Delete user"
                                />
                              }
                            >
                              <Trash2 className="size-3.5" />
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Delete {u.email}?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  This permanently deletes the user and all their data. This
                                  cannot be undone.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                  onClick={() => handleDelete(u.id)}
                                >
                                  Delete permanently
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
