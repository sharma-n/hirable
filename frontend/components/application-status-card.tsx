"use client";

import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

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
  APPLICATION_STAGES,
  apiCompileDocument,
  apiGetApplication,
  apiGetApplicationForJob,
  apiGetDocument,
  apiPatchApplication,
  apiSubmitApplication,
  type ApplicationDetail,
  type ApplicationStage,
} from "@/lib/api";

export interface ApplicationStatusHandle {
  /** Called by the parent page when the agent's change_application_status
   * tool_result arrives. */
  refetch: () => void;
}

interface ApplicationStatusCardProps {
  jobId: string;
  highlighted?: boolean;
}

export const ApplicationStatusCard = forwardRef<ApplicationStatusHandle, ApplicationStatusCardProps>(
  function ApplicationStatusCard({ jobId, highlighted }, ref) {
    const [application, setApplication] = useState<ApplicationDetail | "loading" | null>("loading");
    const [nextAction, setNextAction] = useState("");
    const [notes, setNotes] = useState("");
    const [dirty, setDirty] = useState(false);
    const [saving, setSaving] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [stageSaving, setStageSaving] = useState(false);
    const [previewingId, setPreviewingId] = useState<string | null>(null);

    async function load() {
      const item = await apiGetApplicationForJob(jobId);
      if (!item) {
        setApplication(null);
        return;
      }
      const detail = await apiGetApplication(item.id);
      setApplication(detail);
      setNextAction(detail.next_action ?? "");
      setNotes(detail.notes ?? "");
      setDirty(false);
    }

    useEffect(() => {
      load().catch((err) => {
        toast.error(err instanceof Error ? err.message : "Failed to load application status");
        setApplication(null);
      });
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [jobId]);

    useImperativeHandle(ref, () => ({
      refetch: () => {
        load().catch(() => {
          // non-fatal — the card just keeps showing whatever it had
        });
      },
    }));

    async function handleStageChange(stage: ApplicationStage) {
      if (!application || application === "loading") return;
      setStageSaving(true);
      try {
        const updated = await apiPatchApplication(application.id, { stage });
        setApplication(updated);
        toast.success(`Stage updated to ${stage}`);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to update stage");
      } finally {
        setStageSaving(false);
      }
    }

    async function handleSubmit() {
      if (!application || application === "loading") return;
      setSubmitting(true);
      try {
        const result = await apiSubmitApplication(application.id);
        setApplication(result.application);
        setNextAction(result.application.next_action ?? "");
        setNotes(result.application.notes ?? "");
        if (result.missing_documents.length > 0) {
          toast.success(
            `Submitted — no ${result.missing_documents.join(" or ")} was finalized (none drafted yet).`,
          );
        } else {
          toast.success("Application submitted — CV and cover letter finalized.");
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to submit application");
      } finally {
        setSubmitting(false);
      }
    }

    async function handleSaveNotes() {
      if (!application || application === "loading") return;
      setSaving(true);
      try {
        const updated = await apiPatchApplication(application.id, {
          next_action: nextAction,
          notes,
        });
        setApplication(updated);
        setDirty(false);
        toast.success("Saved");
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to save");
      } finally {
        setSaving(false);
      }
    }

    async function handlePreview(documentId: string) {
      setPreviewingId(documentId);
      try {
        const doc = await apiGetDocument(documentId);
        const blob = await apiCompileDocument(doc.source_text);
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank");
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to preview document");
      } finally {
        setPreviewingId(null);
      }
    }

    if (application === "loading") {
      return (
        <Card>
          <CardContent className="flex items-center justify-center py-8">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </CardContent>
        </Card>
      );
    }

    if (application === null) {
      return null;
    }

    return (
      <Card
        className={
          highlighted ? "ring-2 ring-primary shadow-md transition-shadow duration-700" : undefined
        }
      >
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-base">Application status</CardTitle>
            <div className="flex items-center gap-2">
              <select
                className="rounded-md border bg-background px-2 py-1 text-xs"
                value={application.stage}
                disabled={stageSaving}
                onChange={(e) => handleStageChange(e.target.value as ApplicationStage)}
                aria-label="Application stage"
              >
                {APPLICATION_STAGES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              {application.submitted_at ? (
                <Badge variant="secondary">
                  Submitted {new Date(application.submitted_at).toLocaleDateString()}
                </Badge>
              ) : (
                <AlertDialog>
                  <AlertDialogTrigger render={<Button size="sm" />}>
                    Submit application
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Submit this application?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This finalizes the latest CV and cover-letter drafts as the exact
                        documents submitted, and moves the stage to Applied.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={handleSubmit} disabled={submitting}>
                        {submitting && <Loader2 className="size-4 animate-spin mr-1.5" />}
                        Submit
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>Next action</Label>
            <Input
              value={nextAction}
              onChange={(e) => {
                setNextAction(e.target.value);
                setDirty(true);
              }}
              placeholder="Follow up next week"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Notes</Label>
            <Textarea
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value);
                setDirty(true);
              }}
              rows={3}
            />
          </div>
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!dirty || saving}
              onClick={handleSaveNotes}
            >
              {saving && <Loader2 className="size-4 animate-spin mr-1.5" />}
              Save
            </Button>
          </div>

          {application.documents.length > 0 && (
            <div className="space-y-1.5">
              <Label>Finalized documents</Label>
              <div className="flex flex-wrap gap-2">
                {application.documents.map((d) => (
                  <Button
                    key={d.id}
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={previewingId === d.document_id}
                    onClick={() => handlePreview(d.document_id)}
                  >
                    {previewingId === d.document_id && (
                      <Loader2 className="size-4 animate-spin mr-1.5" />
                    )}
                    {d.doc_type === "cv" ? "CV" : "Cover letter"} (submitted)
                  </Button>
                ))}
              </div>
            </div>
          )}

          {application.events.length > 0 && (
            <div className="space-y-1.5">
              <Label>History</Label>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {application.events
                  .slice()
                  .reverse()
                  .map((e) => (
                    <li key={e.id}>
                      {new Date(e.at).toLocaleString()} — {e.from_stage ?? "(created)"} →{" "}
                      {e.to_stage}
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    );
  },
);
