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
  ChevronRight,
  Sparkles,
  History,
  Undo2,
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
import { AgentPanel } from "@/components/agent-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  apiGetProfile,
  apiListProfileVersions,
  apiRestoreProfileVersion,
  apiUpdateProfile,
  apiUploadResume,
  type Profile,
  type ProfileData,
  type ProfileVersion,
} from "@/lib/api";

// Sections written by the profile-enrichment tools (update_profile_section /
// add_profile_item / record_clarification) — used to diff old vs. new profile
// data and briefly highlight whichever section(s) the agent just touched.
const PROFILE_SECTION_KEYS = [
  "contact",
  "summary",
  "skills",
  "experience",
  "projects",
  "publications",
  "education",
  "extras",
  "enrichment",
] as const;

function changedSections(a: ProfileData, b: ProfileData): string[] {
  return PROFILE_SECTION_KEYS.filter(
    (key) => JSON.stringify(a[key]) !== JSON.stringify(b[key]),
  );
}

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

function SectionCard({
  title,
  highlighted,
  children,
}: {
  title: string;
  highlighted?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);

  // Force the section open when the agent just touched it, so the highlighted
  // change is actually visible rather than hidden behind a collapsed header.
  useEffect(() => {
    if (highlighted) setOpen(true);
  }, [highlighted]);

  return (
    <Card
      className={cn(
        "transition-shadow duration-700",
        highlighted && "ring-2 ring-primary shadow-md",
      )}
    >
      <CardHeader className="pb-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 w-full text-left"
        >
          {open ? (
            <ChevronDown className="size-4 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground shrink-0" />
          )}
          <CardTitle className="text-base flex items-center gap-2">{title}</CardTitle>
          {highlighted && (
            <Badge variant="secondary" className="text-[10px]">
              Updated by agent
            </Badge>
          )}
        </button>
      </CardHeader>
      {open && <CardContent className="space-y-4">{children}</CardContent>}
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

function ContactSection({
  form,
  highlighted,
}: {
  form: UseFormReturn<ProfileFormValues>;
  highlighted?: boolean;
}) {
  const { register, control } = form;
  const { fields: snFields, append: snAppend, remove: snRemove } = useFieldArray({
    control,
    name: "contact.socialNetworks",
  });

  return (
    <SectionCard title="Contact" highlighted={highlighted}>
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

function SummarySection({
  form,
  highlighted,
}: {
  form: UseFormReturn<ProfileFormValues>;
  highlighted?: boolean;
}) {
  return (
    <SectionCard title="Summary" highlighted={highlighted}>
      <Textarea {...form.register("summary")} placeholder="A brief professional summary…" rows={4} />
    </SectionCard>
  );
}

function SkillsSection({
  form,
  highlighted,
}: {
  form: UseFormReturn<ProfileFormValues>;
  highlighted?: boolean;
}) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "skills" });

  return (
    <SectionCard title="Skills" highlighted={highlighted}>
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

function ExperienceSection({
  form,
  highlighted,
}: {
  form: UseFormReturn<ProfileFormValues>;
  highlighted?: boolean;
}) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "experience" });

  return (
    <SectionCard title="Experience" highlighted={highlighted}>
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

function ProjectsSection({
  form,
  highlighted,
}: {
  form: UseFormReturn<ProfileFormValues>;
  highlighted?: boolean;
}) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "projects" });

  return (
    <SectionCard title="Projects" highlighted={highlighted}>
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

function PublicationsSection({
  form,
  highlighted,
}: {
  form: UseFormReturn<ProfileFormValues>;
  highlighted?: boolean;
}) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "publications" });

  return (
    <SectionCard title="Publications" highlighted={highlighted}>
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

function EducationSection({
  form,
  highlighted,
}: {
  form: UseFormReturn<ProfileFormValues>;
  highlighted?: boolean;
}) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "education" });

  return (
    <SectionCard title="Education" highlighted={highlighted}>
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

function ExtrasSection({
  form,
  highlighted,
}: {
  form: UseFormReturn<ProfileFormValues>;
  highlighted?: boolean;
}) {
  const { register, control } = form;
  const { fields, append, remove, move } = useFieldArray({ control, name: "extras" });

  return (
    <SectionCard title="Extras" highlighted={highlighted}>
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

function EnrichmentSection({
  items,
  highlighted,
}: {
  items: { key: string; value: string }[];
  highlighted?: boolean;
}) {
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (highlighted) setOpen(true);
  }, [highlighted]);

  return (
    <Card className={cn("transition-shadow duration-700", highlighted && "ring-2 ring-primary shadow-md")}>
      <CardHeader className="pb-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 w-full text-left"
        >
          {open ? (
            <ChevronDown className="size-4 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground shrink-0" />
          )}
          <Sparkles className="size-4 text-primary shrink-0" />
          <CardTitle className="text-base">Clarifications</CardTitle>
          {highlighted && (
            <Badge variant="secondary" className="text-[10px]">
              Updated by agent
            </Badge>
          )}
        </button>
        {open && (
          <CardDescription>
            Answers the assistant has recorded from chatting with you in the profile panel.
          </CardDescription>
        )}
      </CardHeader>
      {open && (
        <CardContent>
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nothing recorded yet — chat with the assistant on the left to fill in profile gaps.
            </p>
          ) : (
            <ul className="space-y-2">
              {items.map((item, i) => (
                <li key={i} className="text-sm">
                  <span className="font-medium">{item.key}:</span>{" "}
                  <span className="text-muted-foreground">{item.value}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      )}
    </Card>
  );
}

function SOURCE_LABEL(source: ProfileVersion["source"]): string {
  if (source === "agent") return "Before the assistant's edits";
  if (source === "restore") return "Before a restore";
  return "Before your edit";
}

function VersionHistorySection({
  onRestore,
  isDirty,
}: {
  onRestore: (versionId: string) => Promise<void>;
  isDirty: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [versions, setVersions] = useState<ProfileVersion[] | "loading" | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  useEffect(() => {
    if (open && versions === null) {
      setVersions("loading");
      apiListProfileVersions()
        .then(setVersions)
        .catch(() => setVersions([]));
    }
  }, [open, versions]);

  async function handleRestore(versionId: string) {
    setRestoringId(versionId);
    try {
      await onRestore(versionId);
      setVersions(null); // force a refetch next time the list is opened
      setOpen(false);
    } finally {
      setRestoringId(null);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 w-full text-left"
        >
          {open ? (
            <ChevronDown className="size-4 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground shrink-0" />
          )}
          <History className="size-4 text-muted-foreground shrink-0" />
          <CardTitle className="text-base">Version history</CardTitle>
        </button>
      </CardHeader>
      {open && (
        <CardContent>
          {versions === "loading" || versions === null ? (
            <div className="flex justify-center py-4">
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            </div>
          ) : versions.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No earlier versions yet — this fills in as you and the assistant make changes.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {versions.map((v) => (
                <li
                  key={v.id}
                  className="flex items-center justify-between gap-2 text-sm rounded-lg px-2.5 py-1.5 hover:bg-muted/50"
                >
                  <span>
                    {SOURCE_LABEL(v.source)}{" "}
                    <span className="text-muted-foreground">
                      · {new Date(v.created_at).toLocaleString()}
                    </span>
                  </span>
                  <AlertDialog>
                    <AlertDialogTrigger
                      render={
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={restoringId !== null}
                        />
                      }
                    >
                      {restoringId === v.id ? (
                        <Loader2 className="size-3.5 animate-spin mr-1.5" />
                      ) : (
                        <Undo2 className="size-3.5 mr-1.5" />
                      )}
                      Restore
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Restore this version?</AlertDialogTitle>
                        <AlertDialogDescription>
                          Your current profile will be saved as a version too, so this restore
                          can itself be undone.
                          {isDirty && " Any unsaved edits in the form will be discarded."}
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={() => handleRestore(v.id)}>
                          Restore
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      )}
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
              ? "This may take a few minutes."
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
  const [highlightSections, setHighlightSections] = useState<string[]>([]);
  const reUploadInputRef = useRef<HTMLInputElement>(null);
  const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  useEffect(() => {
    return () => {
      if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
    };
  }, []);

  async function handleAgentToolResult(name: string, ok: boolean) {
    if (!ok) return;
    if (!["update_profile_section", "add_profile_item", "record_clarification"].includes(name)) {
      return;
    }
    try {
      const updated = await apiGetProfile();
      if (!updated) return;
      if (form.formState.isDirty) {
        toast.info("The assistant updated your profile — reload to see the changes.");
        return;
      }
      const changed = profile && profile !== "loading" ? changedSections(profile.data, updated.data) : [];
      setProfile(updated);
      form.reset(profileToForm(updated.data));
      setHighlightSections(changed);
      if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
      highlightTimeoutRef.current = setTimeout(() => setHighlightSections([]), 4000);
    } catch {
      // Non-fatal — the user's next manual refresh will pick up the change.
    }
  }

  async function handleRestoreVersion(versionId: string) {
    try {
      const updated = await apiRestoreProfileVersion(versionId);
      const changed = profile && profile !== "loading" ? changedSections(profile.data, updated.data) : [];
      setProfile(updated);
      form.reset(profileToForm(updated.data));
      setHighlightSections(changed);
      if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
      highlightTimeoutRef.current = setTimeout(() => setHighlightSections([]), 4000);
      toast.success(`Restored — now v${updated.version}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Restore failed");
    }
  }

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

  let rightPane: React.ReactNode;
  if (profile === "loading") {
    rightPane = (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  } else if (profile === null) {
    rightPane = <Dropzone onUpload={handleUpload} uploading={uploading} />;
  } else {
    rightPane = (
      <div className="max-w-3xl w-full px-4 py-8 space-y-6">
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
          <VersionHistorySection onRestore={handleRestoreVersion} isDirty={form.formState.isDirty} />
          <ContactSection form={form} highlighted={highlightSections.includes("contact")} />
          <SummarySection form={form} highlighted={highlightSections.includes("summary")} />
          <SkillsSection form={form} highlighted={highlightSections.includes("skills")} />
          <ExperienceSection form={form} highlighted={highlightSections.includes("experience")} />
          <ProjectsSection form={form} highlighted={highlightSections.includes("projects")} />
          <PublicationsSection form={form} highlighted={highlightSections.includes("publications")} />
          <EducationSection form={form} highlighted={highlightSections.includes("education")} />
          <ExtrasSection form={form} highlighted={highlightSections.includes("extras")} />
          <EnrichmentSection
            items={profile.data.enrichment}
            highlighted={highlightSections.includes("enrichment")}
          />
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

  return (
    <div className="flex items-start gap-4 p-4">
      <div className="w-[380px] shrink-0 sticky top-[4.5rem] h-[calc(100vh_-_5.5rem)] flex flex-col">
        <AgentPanel
          conversationBase="profile"
          emptyStateTitle="Let's fill the gaps in your profile"
          emptyStateSubtitle="Ask me to review your profile, or just tell me about your experience — I'll ask questions and save what you tell me."
          starterPrompt="Please review my profile and ask me questions to help fill in any gaps."
          onToolResult={handleAgentToolResult}
        />
      </div>
      <div className="flex-1 min-w-0 flex justify-center">{rightPane}</div>
    </div>
  );
}
