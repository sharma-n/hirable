"use client";

import { useEffect, useRef, useState } from "react";
import { useForm, useFieldArray, type UseFormReturn } from "react-hook-form";
import {
  Plus,
  Trash2,
  Upload,
  Loader2,
  ChevronUp,
  ChevronDown,
  Sparkles,
} from "lucide-react";
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  apiGetProfile,
  apiUpdateProfile,
  apiUploadResume,
  type Profile,
  type ProfileData,
} from "@/lib/api";

// ── Form types ──────────────────────────────────────────────────────────────

type SocialNetworkForm = { network: string; username: string };

type ContactForm = {
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  website: string;
  socialNetworks: SocialNetworkForm[];
  linksText: string;
};

type ExperienceForm = {
  company: string;
  position: string;
  start_date: string;
  end_date: string;
  date: string;
  location: string;
  summary: string;
  highlightsText: string;
  techText: string;
};

type ProjectForm = {
  name: string;
  link: string;
  start_date: string;
  end_date: string;
  date: string;
  location: string;
  summary: string;
  highlightsText: string;
  techText: string;
};

type EducationForm = {
  institution: string;
  area: string;
  degree: string;
  start_date: string;
  end_date: string;
  date: string;
  location: string;
  summary: string;
  highlightsText: string;
};

type PublicationForm = {
  title: string;
  authorsText: string;
  doi: string;
  url: string;
  journal: string;
  summary: string;
  date: string;
};

type ExtrasForm = {
  title: string;
  highlightsText: string;
  techText: string;
};

type ProfileFormValues = {
  contact: ContactForm;
  summary: string;
  skills: { label: string; details: string }[];
  experience: ExperienceForm[];
  projects: ProjectForm[];
  publications: PublicationForm[];
  education: EducationForm[];
  extras: ExtrasForm[];
};

// ── Converters ──────────────────────────────────────────────────────────────

function profileToForm(data: ProfileData): ProfileFormValues {
  return {
    contact: {
      name: data.contact.name,
      headline: data.contact.headline,
      email: data.contact.email,
      phone: data.contact.phone,
      location: data.contact.location,
      website: data.contact.website,
      socialNetworks: data.contact.social_networks.map((sn) => ({
        network: sn.network,
        username: sn.username,
      })),
      linksText: data.contact.links.join("\n"),
    },
    summary: data.summary,
    skills: data.skills.map((s) => ({ label: s.label, details: s.details })),
    experience: data.experience.map((e) => ({
      company: e.company,
      position: e.position,
      start_date: e.start_date,
      end_date: e.end_date,
      date: e.date,
      location: e.location,
      summary: e.summary,
      highlightsText: e.highlights.join("\n"),
      techText: e.tech.join(", "),
    })),
    projects: data.projects.map((p) => ({
      name: p.name,
      link: p.link,
      start_date: p.start_date,
      end_date: p.end_date,
      date: p.date,
      location: p.location,
      summary: p.summary,
      highlightsText: p.highlights.join("\n"),
      techText: p.tech.join(", "),
    })),
    publications: data.publications.map((pub) => ({
      title: pub.title,
      authorsText: pub.authors.join(", "),
      doi: pub.doi,
      url: pub.url,
      journal: pub.journal,
      summary: pub.summary,
      date: pub.date,
    })),
    education: data.education.map((ed) => ({
      institution: ed.institution,
      area: ed.area,
      degree: ed.degree,
      start_date: ed.start_date,
      end_date: ed.end_date,
      date: ed.date,
      location: ed.location,
      summary: ed.summary,
      highlightsText: ed.highlights.join("\n"),
    })),
    extras: data.extras.map((ex) => ({
      title: ex.title,
      highlightsText: ex.highlights.join("\n"),
      techText: ex.tech.join(", "),
    })),
  };
}

function formToProfile(values: ProfileFormValues): ProfileData {
  const splitLines = (text: string) =>
    text
      .split("\n")
      .map((s) => s.replace(/^[-•]\s*/, "").trim())
      .filter(Boolean);
  const splitCommas = (text: string) =>
    text
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

  return {
    contact: {
      name: values.contact.name,
      headline: values.contact.headline,
      email: values.contact.email,
      phone: values.contact.phone,
      location: values.contact.location,
      website: values.contact.website,
      social_networks: values.contact.socialNetworks.filter(
        (sn) => sn.network && sn.username,
      ),
      links: splitLines(values.contact.linksText),
    },
    summary: values.summary,
    skills: values.skills.filter((s) => s.label),
    experience: values.experience.map((e) => ({
      company: e.company,
      position: e.position,
      start_date: e.start_date,
      end_date: e.end_date,
      date: e.date,
      location: e.location,
      summary: e.summary,
      highlights: splitLines(e.highlightsText),
      tech: splitCommas(e.techText),
    })),
    projects: values.projects.map((p) => ({
      name: p.name,
      link: p.link,
      start_date: p.start_date,
      end_date: p.end_date,
      date: p.date,
      location: p.location,
      summary: p.summary,
      highlights: splitLines(p.highlightsText),
      tech: splitCommas(p.techText),
    })),
    publications: values.publications.map((pub) => ({
      title: pub.title,
      authors: splitCommas(pub.authorsText),
      doi: pub.doi,
      url: pub.url,
      journal: pub.journal,
      summary: pub.summary,
      date: pub.date,
    })),
    education: values.education.map((ed) => ({
      institution: ed.institution,
      area: ed.area,
      degree: ed.degree,
      start_date: ed.start_date,
      end_date: ed.end_date,
      date: ed.date,
      location: ed.location,
      summary: ed.summary,
      highlights: splitLines(ed.highlightsText),
    })),
    extras: values.extras.map((ex) => ({
      title: ex.title,
      highlights: splitLines(ex.highlightsText),
      tech: splitCommas(ex.techText),
    })),
    enrichment: [],
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

function ItemHeader({
  label,
  index,
  total,
  onMoveUp,
  onMoveDown,
  onRemove,
}: {
  label: string;
  index: number;
  total: number;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-center gap-1 mb-3">
      <span className="text-xs font-medium text-muted-foreground flex-1">{label}</span>
      <Button type="button" size="icon-sm" variant="ghost" disabled={index === 0} onClick={onMoveUp} aria-label="Move up">
        <ChevronUp className="size-3.5" />
      </Button>
      <Button type="button" size="icon-sm" variant="ghost" disabled={index === total - 1} onClick={onMoveDown} aria-label="Move down">
        <ChevronDown className="size-3.5" />
      </Button>
      <Button type="button" size="icon-sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={onRemove} aria-label="Remove">
        <Trash2 className="size-3.5" />
      </Button>
    </div>
  );
}

// ── Section components ───────────────────────────────────────────────────────

function ContactSection({ form }: { form: UseFormReturn<ProfileFormValues> }) {
  const { register, control } = form;
  const { fields: snFields, append: snAppend, remove: snRemove } = useFieldArray({
    control,
    name: "contact.socialNetworks",
  });

  return (
    <SectionCard title="Contact">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Name">
          <Input {...register("contact.name")} placeholder="Jane Doe" />
        </Field>
        <Field label="Headline">
          <Input {...register("contact.headline")} placeholder="Senior Software Engineer" />
        </Field>
        <Field label="Email">
          <Input {...register("contact.email")} placeholder="jane@example.com" />
        </Field>
        <Field label="Phone">
          <Input {...register("contact.phone")} placeholder="+1 555-0100" />
        </Field>
        <Field label="Location">
          <Input {...register("contact.location")} placeholder="San Francisco, CA" />
        </Field>
        <Field label="Website">
          <Input {...register("contact.website")} placeholder="https://janedoe.dev" />
        </Field>
      </div>

      <div className="space-y-2">
        <Label>Social networks</Label>
        {snFields.map((field, i) => (
          <div key={field.id} className="flex gap-2 items-center">
            <Input
              {...register(`contact.socialNetworks.${i}.network`)}
              placeholder="LinkedIn"
              className="w-36 shrink-0"
            />
            <Input
              {...register(`contact.socialNetworks.${i}.username`)}
              placeholder="jane-doe"
              className="flex-1"
            />
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              className="text-destructive hover:text-destructive shrink-0"
              onClick={() => snRemove(i)}
              aria-label="Remove"
            >
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => snAppend({ network: "", username: "" })}
        >
          <Plus className="size-3.5 mr-1.5" />
          Add social network
        </Button>
      </div>

      <Field label="Other links (one per line)">
        <Textarea
          {...register("contact.linksText")}
          placeholder={"https://scholar.google.com/…\nhttps://orcid.org/…"}
          rows={2}
        />
      </Field>
    </SectionCard>
  );
}

function SummarySection({ form }: { form: UseFormReturn<ProfileFormValues> }) {
  return (
    <SectionCard title="Summary">
      <Textarea {...form.register("summary")} placeholder="A brief professional summary…" rows={4} />
    </SectionCard>
  );
}

function SkillsSection({ form }: { form: UseFormReturn<ProfileFormValues> }) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "skills" });

  return (
    <SectionCard title="Skills">
      <p className="text-xs text-muted-foreground -mt-2">
        Group related skills — e.g. label "Programming Languages", details "Python, Go, TypeScript"
      </p>
      <div className="space-y-2">
        {fields.map((field, i) => (
          <div key={field.id} className="flex gap-2 items-center">
            <Input
              {...register(`skills.${i}.label`)}
              placeholder="Category"
              className="w-44 shrink-0"
            />
            <Input
              {...register(`skills.${i}.details`)}
              placeholder="Python, Go, TypeScript"
              className="flex-1"
            />
            <Button type="button" size="icon-sm" variant="ghost" disabled={i === 0} onClick={() => move(i, i - 1)} aria-label="Move up">
              <ChevronUp className="size-3.5" />
            </Button>
            <Button type="button" size="icon-sm" variant="ghost" disabled={i === fields.length - 1} onClick={() => move(i, i + 1)} aria-label="Move down">
              <ChevronDown className="size-3.5" />
            </Button>
            <Button type="button" size="icon-sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={() => remove(i)} aria-label="Remove">
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => append({ label: "", details: "" })}
        >
          <Plus className="size-3.5 mr-1.5" />
          Add skill group
        </Button>
      </div>
    </SectionCard>
  );
}

function ExperienceSection({ form }: { form: UseFormReturn<ProfileFormValues> }) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "experience" });

  return (
    <SectionCard title="Experience">
      <div className="space-y-5">
        {fields.map((field, i) => (
          <div key={field.id} className="border rounded-xl p-4 space-y-3">
            <ItemHeader
              label={`Experience ${i + 1}`}
              index={i}
              total={fields.length}
              onMoveUp={() => move(i, i - 1)}
              onMoveDown={() => move(i, i + 1)}
              onRemove={() => remove(i)}
            />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Company">
                <Input {...register(`experience.${i}.company`)} placeholder="Acme Corp" />
              </Field>
              <Field label="Position">
                <Input {...register(`experience.${i}.position`)} placeholder="Software Engineer" />
              </Field>
              <Field label="Start date">
                <Input {...register(`experience.${i}.start_date`)} placeholder="2021-03" />
              </Field>
              <Field label="End date">
                <Input {...register(`experience.${i}.end_date`)} placeholder="present" />
              </Field>
              <Field label="Location">
                <Input {...register(`experience.${i}.location`)} placeholder="San Francisco, CA" />
              </Field>
              <Field label="Tech (comma-separated)">
                <Input {...register(`experience.${i}.techText`)} placeholder="React, Python, AWS" />
              </Field>
            </div>
            <Field label="Summary (optional, appears above bullets)">
              <Input {...register(`experience.${i}.summary`)} placeholder="Brief role overview…" />
            </Field>
            <Field label="Highlights (one per line)">
              <Textarea
                {...register(`experience.${i}.highlightsText`)}
                placeholder={"Led migration of auth service\nReduced latency by 40%"}
                rows={4}
              />
            </Field>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() =>
            append({
              company: "",
              position: "",
              start_date: "",
              end_date: "",
              date: "",
              location: "",
              summary: "",
              highlightsText: "",
              techText: "",
            })
          }
        >
          <Plus className="size-3.5 mr-1.5" />
          Add experience
        </Button>
      </div>
    </SectionCard>
  );
}

function ProjectsSection({ form }: { form: UseFormReturn<ProfileFormValues> }) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "projects" });

  return (
    <SectionCard title="Projects">
      <div className="space-y-5">
        {fields.map((field, i) => (
          <div key={field.id} className="border rounded-xl p-4 space-y-3">
            <ItemHeader
              label={`Project ${i + 1}`}
              index={i}
              total={fields.length}
              onMoveUp={() => move(i, i - 1)}
              onMoveDown={() => move(i, i + 1)}
              onRemove={() => remove(i)}
            />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Name">
                <Input {...register(`projects.${i}.name`)} placeholder="hirable" />
              </Field>
              <Field label="Link">
                <Input {...register(`projects.${i}.link`)} placeholder="https://github.com/…" />
              </Field>
              <Field label="Start date">
                <Input {...register(`projects.${i}.start_date`)} placeholder="2023-01" />
              </Field>
              <Field label="End date">
                <Input {...register(`projects.${i}.end_date`)} placeholder="present" />
              </Field>
            </div>
            <Field label="Tech (comma-separated)">
              <Input {...register(`projects.${i}.techText`)} placeholder="Next.js, FastAPI, Docker" />
            </Field>
            <Field label="Summary (optional)">
              <Input {...register(`projects.${i}.summary`)} placeholder="Brief project description…" />
            </Field>
            <Field label="Highlights (one per line)">
              <Textarea
                {...register(`projects.${i}.highlightsText`)}
                placeholder={"Self-hosted job application assistant\nMulti-user with session auth"}
                rows={3}
              />
            </Field>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() =>
            append({
              name: "",
              link: "",
              start_date: "",
              end_date: "",
              date: "",
              location: "",
              summary: "",
              highlightsText: "",
              techText: "",
            })
          }
        >
          <Plus className="size-3.5 mr-1.5" />
          Add project
        </Button>
      </div>
    </SectionCard>
  );
}

function PublicationsSection({ form }: { form: UseFormReturn<ProfileFormValues> }) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "publications" });

  return (
    <SectionCard title="Publications">
      <div className="space-y-5">
        {fields.map((field, i) => (
          <div key={field.id} className="border rounded-xl p-4 space-y-3">
            <ItemHeader
              label={`Publication ${i + 1}`}
              index={i}
              total={fields.length}
              onMoveUp={() => move(i, i - 1)}
              onMoveDown={() => move(i, i + 1)}
              onRemove={() => remove(i)}
            />
            <Field label="Title">
              <Input {...register(`publications.${i}.title`)} placeholder="Sparse Mixture-of-Experts at Scale" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Authors (comma-separated; *You* to highlight)">
                <Input {...register(`publications.${i}.authorsText`)} placeholder="*Jane Doe*, John Smith" />
              </Field>
              <Field label="Date">
                <Input {...register(`publications.${i}.date`)} placeholder="2023-07" />
              </Field>
              <Field label="Journal / Venue">
                <Input {...register(`publications.${i}.journal`)} placeholder="NeurIPS 2023" />
              </Field>
              <Field label="DOI">
                <Input {...register(`publications.${i}.doi`)} placeholder="10.1234/…" />
              </Field>
              <Field label="URL">
                <Input {...register(`publications.${i}.url`)} placeholder="https://arxiv.org/…" />
              </Field>
            </div>
            <Field label="Summary (optional)">
              <Input {...register(`publications.${i}.summary`)} placeholder="One-line description…" />
            </Field>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() =>
            append({
              title: "",
              authorsText: "",
              doi: "",
              url: "",
              journal: "",
              summary: "",
              date: "",
            })
          }
        >
          <Plus className="size-3.5 mr-1.5" />
          Add publication
        </Button>
      </div>
    </SectionCard>
  );
}

function EducationSection({ form }: { form: UseFormReturn<ProfileFormValues> }) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "education" });

  return (
    <SectionCard title="Education">
      <div className="space-y-5">
        {fields.map((field, i) => (
          <div key={field.id} className="border rounded-xl p-4 space-y-3">
            <ItemHeader
              label={`Education ${i + 1}`}
              index={i}
              total={fields.length}
              onMoveUp={() => move(i, i - 1)}
              onMoveDown={() => move(i, i + 1)}
              onRemove={() => remove(i)}
            />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Institution">
                <Input {...register(`education.${i}.institution`)} placeholder="MIT" />
              </Field>
              <Field label="Degree">
                <Input {...register(`education.${i}.degree`)} placeholder="B.S." />
              </Field>
              <Field label="Area (field of study)">
                <Input {...register(`education.${i}.area`)} placeholder="Computer Science" />
              </Field>
              <Field label="Location">
                <Input {...register(`education.${i}.location`)} placeholder="Cambridge, MA" />
              </Field>
              <Field label="Start date">
                <Input {...register(`education.${i}.start_date`)} placeholder="2016" />
              </Field>
              <Field label="End date">
                <Input {...register(`education.${i}.end_date`)} placeholder="2020" />
              </Field>
            </div>
            <Field label="Summary (optional)">
              <Input {...register(`education.${i}.summary`)} placeholder="Brief programme description…" />
            </Field>
            <Field label="Highlights (GPA, honours, coursework — one per line)">
              <Textarea
                {...register(`education.${i}.highlightsText`)}
                placeholder={"GPA: 3.9/4.0\nNSF Fellowship\nRelevant coursework: Distributed Systems, ML"}
                rows={3}
              />
            </Field>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() =>
            append({
              institution: "",
              area: "",
              degree: "",
              start_date: "",
              end_date: "",
              date: "",
              location: "",
              summary: "",
              highlightsText: "",
            })
          }
        >
          <Plus className="size-3.5 mr-1.5" />
          Add education
        </Button>
      </div>
    </SectionCard>
  );
}

function ExtrasSection({ form }: { form: UseFormReturn<ProfileFormValues> }) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "extras" });

  return (
    <SectionCard title="Extras">
      <p className="text-xs text-muted-foreground -mt-2">
        Patents, talks, awards, certifications, volunteering, interests…
      </p>
      <div className="space-y-5">
        {fields.map((field, i) => (
          <div key={field.id} className="border rounded-xl p-4 space-y-3">
            <ItemHeader
              label={`Entry ${i + 1}`}
              index={i}
              total={fields.length}
              onMoveUp={() => move(i, i - 1)}
              onMoveDown={() => move(i, i + 1)}
              onRemove={() => remove(i)}
            />
            <Field label="Title">
              <Input {...register(`extras.${i}.title`)} placeholder="Open Source Contributions" />
            </Field>
            <Field label="Tech (comma-separated, if applicable)">
              <Input {...register(`extras.${i}.techText`)} placeholder="Python, Rust" />
            </Field>
            <Field label="Highlights (one per line)">
              <Textarea
                {...register(`extras.${i}.highlightsText`)}
                placeholder={"Contributed to FastAPI\nMaintainer of open-cli"}
                rows={3}
              />
            </Field>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => append({ title: "", highlightsText: "", techText: "" })}
        >
          <Plus className="size-3.5 mr-1.5" />
          Add entry
        </Button>
      </div>
    </SectionCard>
  );
}

function EnrichmentStub() {
  return (
    <Card className="opacity-60">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-primary" />
          <CardTitle className="text-base">Profile enrichment</CardTitle>
          <Badge variant="secondary" className="text-xs ml-1">
            Coming in M4
          </Badge>
        </div>
        <CardDescription>
          Chat with the assistant to fill in profile gaps — target role, job-search context, and
          extra details the agent uses when tailoring your CV.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button variant="outline" size="sm" disabled>
          Start enrichment session
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Dropzone ─────────────────────────────────────────────────────────────────

function Dropzone({
  onUpload,
  uploading,
}: {
  onUpload: (file: File) => void;
  uploading: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onUpload(file);
  }

  return (
    <div className="flex flex-col items-center justify-center flex-1 p-8">
      <div
        role="button"
        tabIndex={0}
        onClick={() => !uploading && inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && !uploading && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "w-full max-w-lg border-2 border-dashed rounded-2xl p-14 flex flex-col items-center gap-4 cursor-pointer select-none transition-colors",
          dragging
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-muted/30",
          uploading && "pointer-events-none opacity-60",
        )}
      >
        {uploading ? (
          <Loader2 className="size-10 text-primary animate-spin" />
        ) : (
          <Upload className="size-10 text-muted-foreground" />
        )}
        <div className="text-center">
          <p className="font-medium">
            {uploading ? "Parsing resume…" : "Upload your resume"}
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            {uploading
              ? "This may take a few seconds."
              : "Drag & drop or click to browse. Accepts PDF, DOCX, and TeX."}
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.tex"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onUpload(file);
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

const EMPTY_FORM: ProfileFormValues = {
  contact: {
    name: "",
    headline: "",
    email: "",
    phone: "",
    location: "",
    website: "",
    socialNetworks: [],
    linksText: "",
  },
  summary: "",
  skills: [],
  experience: [],
  projects: [],
  publications: [],
  education: [],
  extras: [],
};

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null | "loading">("loading");
  const [uploading, setUploading] = useState(false);
  const [reUploadOpen, setReUploadOpen] = useState(false);
  const reUploadInputRef = useRef<HTMLInputElement>(null);

  const form = useForm<ProfileFormValues>({ defaultValues: EMPTY_FORM });

  useEffect(() => {
    apiGetProfile()
      .then((p) => {
        setProfile(p);
        if (p) form.reset(profileToForm(p.data));
      })
      .catch(() => {
        toast.error("Failed to load profile");
        setProfile(null);
      });
  }, [form]);

  async function handleUpload(file: File) {
    const startedAt = performance.now();
    const elapsedMs = () => Math.round(performance.now() - startedAt);
    console.info(
      `[resume-upload] selected file=${file.name} type=${file.type || "?"} size=${file.size}B`,
    );

    setUploading(true);
    try {
      console.info("[resume-upload] sending to backend for extraction + parse…");
      const updated = await apiUploadResume(file);
      console.info(
        `[resume-upload] profile ready v${updated.version} in ${elapsedMs()}ms`,
      );
      setProfile(updated);
      form.reset(profileToForm(updated.data));
      toast.success("Resume parsed and profile created.");
    } catch (err) {
      console.error(`[resume-upload] failed after ${elapsedMs()}ms:`, err);
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function onSubmit(values: ProfileFormValues) {
    try {
      const data = formToProfile(values);
      const updated = await apiUpdateProfile(data);
      setProfile(updated);
      form.reset(profileToForm(updated.data));
      toast.success(`Profile saved (v${updated.version})`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    }
  }

  if (profile === "loading") {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (profile === null) {
    return <Dropzone onUpload={handleUpload} uploading={uploading} />;
  }

  return (
    <div className="max-w-3xl mx-auto w-full px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold">Master Profile</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Version {profile.version} · Updated{" "}
            {new Date(profile.updated_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <AlertDialog open={reUploadOpen} onOpenChange={setReUploadOpen}>
            <AlertDialogTrigger
              render={
                <Button
                  variant="outline"
                  size="sm"
                  disabled={uploading || form.formState.isSubmitting}
                />
              }
            >
              {uploading ? (
                <Loader2 className="size-4 animate-spin mr-1.5" />
              ) : (
                <Upload className="size-4 mr-1.5" />
              )}
              Re-upload
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Re-upload resume?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will re-parse your resume and overwrite the current profile. Any manual
                  edits will be lost.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => {
                    setReUploadOpen(false);
                    reUploadInputRef.current?.click();
                  }}
                >
                  Continue
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <input
            ref={reUploadInputRef}
            type="file"
            accept=".pdf,.docx,.tex"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleUpload(file);
              e.target.value = "";
            }}
          />
          <Button
            size="sm"
            disabled={form.formState.isSubmitting || uploading}
            onClick={form.handleSubmit(onSubmit)}
          >
            {form.formState.isSubmitting && (
              <Loader2 className="size-4 animate-spin mr-1.5" />
            )}
            Save
          </Button>
        </div>
      </div>

      {/* Editor */}
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <ContactSection form={form} />
        <SummarySection form={form} />
        <SkillsSection form={form} />
        <ExperienceSection form={form} />
        <ProjectsSection form={form} />
        <PublicationsSection form={form} />
        <EducationSection form={form} />
        <ExtrasSection form={form} />
        <EnrichmentStub />
        <div className="flex justify-end pb-8">
          <Button type="submit" disabled={form.formState.isSubmitting || uploading}>
            {form.formState.isSubmitting && (
              <Loader2 className="size-4 animate-spin mr-1.5" />
            )}
            Save changes
          </Button>
        </div>
      </form>
    </div>
  );
}
