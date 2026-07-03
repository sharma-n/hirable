"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { toast } from "sonner";
import { Loader2, Plus, Trash2 } from "lucide-react";

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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiAddJob, apiDeleteJob, apiListJobs, type Job } from "@/lib/api";

type AddMode = "url" | "paste";

export default function JobsPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[] | "loading">("loading");

  const [mode, setMode] = useState<AddMode>("url");
  const [url, setUrl] = useState("");
  const [rawText, setRawText] = useState("");
  const [needsPaste, setNeedsPaste] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    apiListJobs()
      .then(setJobs)
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : "Failed to load jobs");
        setJobs([]);
      });
  }, []);

  function resetForm() {
    setMode("url");
    setUrl("");
    setRawText("");
    setNeedsPaste(false);
  }

  async function handleAddByUrl() {
    if (!url.trim()) return;
    setSubmitting(true);
    try {
      const result = await apiAddJob({ url: url.trim() });
      if (result.needs_paste) {
        setNeedsPaste(true);
        toast.error("Couldn't fetch that URL — paste the job description text instead.");
        return;
      }
      if (result.job) {
        setJobs((prev) => [result.job as Job, ...(prev === "loading" ? [] : prev)]);
        toast.success("Job added");
        resetForm();
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add job");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAddWithPastedText() {
    if (!rawText.trim()) return;
    setSubmitting(true);
    try {
      const result = await apiAddJob({
        url: needsPaste ? url.trim() : undefined,
        raw_text: rawText.trim(),
      });
      if (result.job) {
        setJobs((prev) => [result.job as Job, ...(prev === "loading" ? [] : prev)]);
        toast.success("Job added");
        resetForm();
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add job");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(jobId: string) {
    try {
      await apiDeleteJob(jobId);
      setJobs((prev) => (prev === "loading" ? prev : prev.filter((j) => j.id !== jobId)));
      toast.success("Job deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="max-w-5xl mx-auto w-full px-4 py-8 space-y-6">
      <div>
        <h1 className="text-xl font-bold">Jobs</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Add postings you're considering and let the assistant tailor documents to them.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Add a job</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {mode === "url" && !needsPaste && (
            <div className="flex gap-2 items-start">
              <div className="flex-1 space-y-1.5">
                <Label>Job posting URL</Label>
                <Input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com/careers/senior-engineer"
                  onKeyDown={(e) => e.key === "Enter" && handleAddByUrl()}
                />
              </div>
              <Button className="mt-6" disabled={submitting || !url.trim()} onClick={handleAddByUrl}>
                {submitting && <Loader2 className="size-4 animate-spin mr-1.5" />}
                <Plus className="size-4 mr-1.5" />
                Add
              </Button>
            </div>
          )}

          {mode === "url" && needsPaste && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                We couldn't fetch <span className="font-medium">{url}</span> — many job boards
                block automated requests. Paste the job description text below instead.
              </p>
              <div className="space-y-1.5">
                <Label>Job posting text</Label>
                <Textarea
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  placeholder="Paste the full job description here…"
                  rows={8}
                />
              </div>
              <div className="flex gap-2">
                <Button disabled={submitting || !rawText.trim()} onClick={handleAddWithPastedText}>
                  {submitting && <Loader2 className="size-4 animate-spin mr-1.5" />}
                  Parse pasted text
                </Button>
                <Button variant="ghost" onClick={resetForm} disabled={submitting}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {mode === "paste" && (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label>Job posting text</Label>
                <Textarea
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  placeholder="Paste the full job description here…"
                  rows={8}
                />
              </div>
              <div className="flex gap-2">
                <Button disabled={submitting || !rawText.trim()} onClick={handleAddWithPastedText}>
                  {submitting && <Loader2 className="size-4 animate-spin mr-1.5" />}
                  <Plus className="size-4 mr-1.5" />
                  Add
                </Button>
                <Button variant="ghost" onClick={resetForm} disabled={submitting}>
                  Use a URL instead
                </Button>
              </div>
            </div>
          )}

          {mode === "url" && !needsPaste && (
            <button
              type="button"
              className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2"
              onClick={() => setMode("paste")}
            >
              Paste text instead
            </button>
          )}
        </CardContent>
      </Card>

      {jobs === "loading" ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : jobs.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-16">
          No jobs yet — add one above to get started.
        </p>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Seniority</TableHead>
                <TableHead>Added</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow
                  key={job.id}
                  className="cursor-pointer"
                  onClick={() => router.push(`/jobs/${job.id}`)}
                >
                  <TableCell className="font-medium">
                    {job.parsed.company || <span className="text-muted-foreground">—</span>}
                  </TableCell>
                  <TableCell>{job.parsed.title || <span className="text-muted-foreground">—</span>}</TableCell>
                  <TableCell className="text-muted-foreground">{job.parsed.location || "—"}</TableCell>
                  <TableCell>
                    {job.parsed.seniority ? (
                      <Badge variant="secondary" className="capitalize">
                        {job.parsed.seniority}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {format(new Date(job.created_at), "MMM d, yyyy")}
                  </TableCell>
                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <AlertDialog>
                      <AlertDialogTrigger
                        render={
                          <Button
                            size="icon-sm"
                            variant="ghost"
                            className="text-destructive hover:text-destructive"
                            title="Delete job"
                          />
                        }
                      >
                        <Trash2 className="size-3.5" />
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>
                            Delete {job.parsed.title || "this job"}?
                          </AlertDialogTitle>
                          <AlertDialogDescription>
                            This permanently removes the job from your shortlist. This cannot be
                            undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            onClick={() => handleDelete(job.id)}
                          >
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
