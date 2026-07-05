"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useForm, type UseFormReturn } from "react-hook-form";
import { ExternalLink, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { AgentPanel } from "@/components/agent-panel";
import { ApplicationStatusCard, type ApplicationStatusHandle } from "@/components/application-status-card";
import { DocumentArtifact, type DocumentArtifactHandle } from "@/components/document-artifact";
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
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { apiDeleteJob, apiGetJob, apiUpdateJob, type Job, type JobData } from "@/lib/api";

// ── Form types ──────────────────────────────────────────────────────────────

type JobFormValues = {
  company: string;
  title: string;
  location: string;
  responsibilitiesText: string;
  mustHaveText: string;
  niceToHaveText: string;
  keywordsText: string;
  why_opened_guess: string;
  seniority: string;
  company_type: string;
  team_name: string;
  team_description: string;
};

const EMPTY_FORM: JobFormValues = {
  company: "",
  title: "",
  location: "",
  responsibilitiesText: "",
  mustHaveText: "",
  niceToHaveText: "",
  keywordsText: "",
  why_opened_guess: "",
  seniority: "",
  company_type: "",
  team_name: "",
  team_description: "",
};

function splitLines(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.replace(/^[-•]\s*/, "").trim())
    .filter(Boolean);
}

function jobToForm(data: JobData): JobFormValues {
  return {
    company: data.company,
    title: data.title,
    location: data.location,
    responsibilitiesText: data.responsibilities.join("\n"),
    mustHaveText: data.must_have.join("\n"),
    niceToHaveText: data.nice_to_have.join("\n"),
    keywordsText: data.keywords.join("\n"),
    why_opened_guess: data.why_opened_guess,
    seniority: data.seniority,
    company_type: data.company_type,
    team_name: data.team_name,
    team_description: data.team_description,
  };
}

function formToJob(values: JobFormValues): JobData {
  return {
    company: values.company,
    title: values.title,
    location: values.location,
    responsibilities: splitLines(values.responsibilitiesText),
    must_have: splitLines(values.mustHaveText),
    nice_to_have: splitLines(values.niceToHaveText),
    keywords: splitLines(values.keywordsText),
    why_opened_guess: values.why_opened_guess,
    seniority: values.seniority,
    company_type: values.company_type,
    team_name: values.team_name,
    team_description: values.team_description,
  };
}

// ── Shared primitives ────────────────────────────────────────────────────────

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

// ── Section components ───────────────────────────────────────────────────────

function RoleSection({ form }: { form: UseFormReturn<JobFormValues> }) {
  const { register } = form;
  return (
    <SectionCard title="Role">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Title">
          <Input {...register("title")} placeholder="Senior Software Engineer" />
        </Field>
        <Field label="Location">
          <Input {...register("location")} placeholder="Remote" />
        </Field>
        <Field label="Seniority">
          <Input {...register("seniority")} placeholder="senior" />
        </Field>
      </div>
      <Field label="Responsibilities (one per line)">
        <Textarea
          {...register("responsibilitiesText")}
          placeholder={"Design and own backend APIs\nMentor junior engineers"}
          rows={5}
        />
      </Field>
    </SectionCard>
  );
}

function RequirementsSection({ form }: { form: UseFormReturn<JobFormValues> }) {
  const { register } = form;
  return (
    <SectionCard title="Requirements">
      <Field label="Must-have (one per line)">
        <Textarea
          {...register("mustHaveText")}
          placeholder={"5+ years of backend experience\nStrong Python skills"}
          rows={4}
        />
      </Field>
      <Field label="Nice-to-have (one per line)">
        <Textarea {...register("niceToHaveText")} placeholder="Kubernetes experience" rows={3} />
      </Field>
      <Field label="Keywords for résumé-tailoring (one per line)">
        <Textarea {...register("keywordsText")} placeholder={"FastAPI\nPostgreSQL"} rows={3} />
      </Field>
    </SectionCard>
  );
}

function TeamCompanySection({ form }: { form: UseFormReturn<JobFormValues> }) {
  const { register } = form;
  return (
    <SectionCard title="Team & company">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Company">
          <Input {...register("company")} placeholder="Acme Corp" />
        </Field>
        <Field label="Company type">
          <Input {...register("company_type")} placeholder="startup" />
        </Field>
        <Field label="Team name">
          <Input {...register("team_name")} placeholder="Payments Platform" />
        </Field>
        <Field label="Team focus">
          <Input {...register("team_description")} placeholder="Owns checkout and billing" />
        </Field>
      </div>
    </SectionCard>
  );
}

function WhyOpenedSection({ form }: { form: UseFormReturn<JobFormValues> }) {
  return (
    <SectionCard title="Why this role likely opened">
      <Textarea {...form.register("why_opened_guess")} rows={2} />
    </SectionCard>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<Job | "loading" | null>("loading");
  const [showRawText, setShowRawText] = useState(false);
  const [cvHighlighted, setCvHighlighted] = useState(false);
  const [letterHighlighted, setLetterHighlighted] = useState(false);
  const [applicationHighlighted, setApplicationHighlighted] = useState(false);
  const cvRef = useRef<DocumentArtifactHandle | null>(null);
  const letterRef = useRef<DocumentArtifactHandle | null>(null);
  const applicationRef = useRef<ApplicationStatusHandle | null>(null);
  const cvHighlightTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const letterHighlightTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const applicationHighlightTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const form = useForm<JobFormValues>({ defaultValues: EMPTY_FORM });

  function handleAgentToolResult(name: string, ok: boolean) {
    if (!ok) return;
    if (["update_profile_section", "add_profile_item", "record_clarification"].includes(name)) {
      toast.info("Your profile was updated based on this conversation — see the Profile page.");
    }
    if (name === "draft_cv") {
      cvRef.current?.refetch();
      setCvHighlighted(true);
      if (cvHighlightTimeout.current) clearTimeout(cvHighlightTimeout.current);
      cvHighlightTimeout.current = setTimeout(() => setCvHighlighted(false), 4000);
    }
    if (name === "draft_cover_letter") {
      letterRef.current?.refetch();
      setLetterHighlighted(true);
      if (letterHighlightTimeout.current) clearTimeout(letterHighlightTimeout.current);
      letterHighlightTimeout.current = setTimeout(() => setLetterHighlighted(false), 4000);
    }
    if (name === "change_application_status") {
      applicationRef.current?.refetch();
      setApplicationHighlighted(true);
      if (applicationHighlightTimeout.current) clearTimeout(applicationHighlightTimeout.current);
      applicationHighlightTimeout.current = setTimeout(() => setApplicationHighlighted(false), 4000);
    }
  }

  useEffect(() => {
    return () => {
      if (cvHighlightTimeout.current) clearTimeout(cvHighlightTimeout.current);
      if (letterHighlightTimeout.current) clearTimeout(letterHighlightTimeout.current);
      if (applicationHighlightTimeout.current) clearTimeout(applicationHighlightTimeout.current);
    };
  }, []);

  useEffect(() => {
    apiGetJob(params.id)
      .then((j) => {
        setJob(j);
        form.reset(jobToForm(j.parsed));
      })
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : "Failed to load job");
        setJob(null);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  async function onSubmit(values: JobFormValues) {
    if (job === "loading" || job === null) return;
    try {
      const data = formToJob(values);
      const updated = await apiUpdateJob(job.id, data);
      setJob(updated);
      form.reset(jobToForm(updated.parsed));
      toast.success("Job saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    }
  }

  async function handleDelete() {
    if (job === "loading" || job === null) return;
    try {
      await apiDeleteJob(job.id);
      toast.success("Job deleted");
      router.push("/jobs");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  }

  let rightPane: React.ReactNode;
  if (job === "loading") {
    rightPane = (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  } else if (job === null) {
    rightPane = (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-muted-foreground">Job not found.</p>
      </div>
    );
  } else {
    rightPane = (
    <div className="max-w-3xl w-full px-4 py-8 flex flex-col">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold">
            {job.parsed.title || "Untitled role"}
            {job.parsed.company && (
              <span className="text-muted-foreground font-normal"> · {job.parsed.company}</span>
            )}
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Updated {new Date(job.updated_at).toLocaleDateString()}
            {job.source_url && (
              <>
                {" · "}
                <a
                  href={job.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 underline underline-offset-2 hover:text-foreground"
                >
                  View original posting
                  <ExternalLink className="size-3" />
                </a>
              </>
            )}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <AlertDialog>
            <AlertDialogTrigger render={<Button variant="outline" size="sm" />}>
              <Trash2 className="size-4 mr-1.5" />
              Delete
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this job?</AlertDialogTitle>
                <AlertDialogDescription>
                  This permanently removes it from your shortlist. This cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  onClick={handleDelete}
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button
            size="sm"
            disabled={form.formState.isSubmitting}
            onClick={form.handleSubmit(onSubmit)}
          >
            {form.formState.isSubmitting && <Loader2 className="size-4 animate-spin mr-1.5" />}
            Save
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="application" className="flex-1 flex flex-col">
        <TabsList className="grid w-full grid-cols-2 mb-6">
          <TabsTrigger value="application">Application</TabsTrigger>
          <TabsTrigger value="job-details">Job details</TabsTrigger>
        </TabsList>

        {/* Application Tab */}
        <TabsContent value="application" className="flex-1 space-y-6">
          <ApplicationStatusCard
            ref={applicationRef}
            jobId={job.id}
            highlighted={applicationHighlighted}
          />
          <DocumentArtifact
            ref={cvRef}
            jobId={job.id}
            documentType="cv"
            title="CV"
            emptyText="No CV drafted yet for this job. Generate one from your tailored profile, or ask the assistant to draft it in the chat."
            generateLabel="Generate CV"
            regenerateLabel="Regenerate"
            highlighted={cvHighlighted}
          />
          <DocumentArtifact
            ref={letterRef}
            jobId={job.id}
            documentType="cover_letter"
            title="Cover letter"
            emptyText="No cover letter drafted yet for this job. Generate one from your tailored profile, or ask the assistant to draft it in the chat."
            generateLabel="Generate cover letter"
            regenerateLabel="Regenerate"
            highlighted={letterHighlighted}
          />
        </TabsContent>

        {/* Job Details Tab */}
        <TabsContent value="job-details" className="flex-1 space-y-6">
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <RoleSection form={form} />
            <RequirementsSection form={form} />
            <TeamCompanySection form={form} />
            <WhyOpenedSection form={form} />

            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Original posting text</CardTitle>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowRawText((v) => !v)}
                  >
                    {showRawText ? "Hide" : "Show"}
                  </Button>
                </div>
              </CardHeader>
              {showRawText && (
                <CardContent>
                  <Textarea value={job.raw_text} readOnly rows={12} className="text-xs" />
                </CardContent>
              )}
            </Card>

            <div className="flex justify-end pb-8">
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && <Loader2 className="size-4 animate-spin mr-1.5" />}
                Save changes
              </Button>
            </div>
          </form>
        </TabsContent>
      </Tabs>
    </div>
    );
  }

  return (
    <div className="flex items-start gap-4 p-4">
      <div className="w-[380px] shrink-0 sticky top-[4.5rem] h-[calc(100vh_-_5.5rem)] flex flex-col">
        <AgentPanel
          conversationBase={`job:${params.id}`}
          emptyStateTitle="Let's see how you match this role"
          emptyStateSubtitle="I'll compare your profile against this job and ask about anything worth clarifying."
          starterPrompt="Please compare my profile against this job and tell me what's missing or could be improved."
          onToolResult={handleAgentToolResult}
        />
      </div>
      <div className="flex-1 min-w-0 flex justify-center">{rightPane}</div>
    </div>
  );
}
