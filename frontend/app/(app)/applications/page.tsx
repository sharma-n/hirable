"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  DndContext,
  type DragEndEvent,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { formatDistanceToNow } from "date-fns";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Badge, type badgeVariants } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  APPLICATION_STAGES,
  apiListApplications,
  apiPatchApplication,
  type ApplicationListItem,
  type ApplicationStage,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import type { VariantProps } from "class-variance-authority";

function stalenessLabel(application: ApplicationListItem): { text: string; overdue: boolean } | null {
  if (!application.auto_stale_at) return null;
  const date = new Date(application.auto_stale_at);
  const overdue = date.getTime() < Date.now();
  return {
    text: overdue
      ? `Stale ${formatDistanceToNow(date)} ago`
      : `Goes stale in ${formatDistanceToNow(date)}`,
    overdue,
  };
}

function stageBadgeVariant(stage: ApplicationStage): VariantProps<typeof badgeVariants>["variant"] {
  if (stage === "Rejected" || stage === "Declined") return "destructive";
  if (stage === "Stale") return "outline";
  if (stage === "Accepted" || stage === "Offer") return "default";
  return "secondary";
}

function ApplicationCard({ application }: { application: ApplicationListItem }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: application.id,
  });
  const style = transform
    ? { transform: CSS.Translate.toString(transform), zIndex: isDragging ? 50 : undefined }
    : undefined;
  const staleness = stalenessLabel(application);

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={cn(
        "touch-none cursor-grab rounded-lg border bg-card p-3 shadow-sm active:cursor-grabbing",
        isDragging && "opacity-50",
      )}
    >
      <Link href={`/jobs/${application.job_id}`} className="text-sm font-medium hover:underline">
        {application.title || "Untitled role"}
      </Link>
      <p className="text-xs text-muted-foreground">{application.company}</p>
      {application.next_action && <p className="mt-1.5 text-xs">{application.next_action}</p>}
      {staleness && (
        <p
          className={cn(
            "mt-1.5 text-xs",
            staleness.overdue ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {staleness.text}
        </p>
      )}
    </div>
  );
}

function BoardColumn({
  stage,
  applications,
}: {
  stage: ApplicationStage;
  applications: ApplicationListItem[];
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex w-64 shrink-0 flex-col gap-2 rounded-lg border bg-muted/30 p-2 transition-colors",
        isOver && "ring-2 ring-primary",
      )}
    >
      <div className="flex items-center justify-between px-1 py-1">
        <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
          {stage}
        </h3>
        <Badge variant="secondary" className="text-xs">
          {applications.length}
        </Badge>
      </div>
      <div className="flex min-h-8 flex-col gap-2">
        {applications.map((a) => (
          <ApplicationCard key={a.id} application={a} />
        ))}
      </div>
    </div>
  );
}

export default function ApplicationsPage() {
  const router = useRouter();
  const [applications, setApplications] = useState<ApplicationListItem[] | "loading">("loading");
  const [stageFilter, setStageFilter] = useState<ApplicationStage | "all">("all");
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  useEffect(() => {
    apiListApplications()
      .then(setApplications)
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : "Failed to load applications");
        setApplications([]);
      });
  }, []);

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || applications === "loading") return;
    const newStage = over.id as ApplicationStage;
    const application = applications.find((a) => a.id === active.id);
    if (!application || application.stage === newStage) return;

    const previous = applications;
    setApplications(
      applications.map((a) => (a.id === application.id ? { ...a, stage: newStage } : a)),
    );
    try {
      await apiPatchApplication(application.id, { stage: newStage });
    } catch (err) {
      setApplications(previous);
      toast.error(err instanceof Error ? err.message : "Failed to update stage");
    }
  }

  const filteredForTable = useMemo(() => {
    if (applications === "loading") return [];
    const filtered = stageFilter === "all" ? applications : applications.filter((a) => a.stage === stageFilter);
    return filtered.slice().sort(
      (a, b) => new Date(a.last_activity_at).getTime() - new Date(b.last_activity_at).getTime(),
    );
  }, [applications, stageFilter]);

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-8">
      <div>
        <h1 className="text-xl font-bold">Applications</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Track every job through the pipeline, from draft to offer.
        </p>
      </div>

      {applications === "loading" ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : applications.length === 0 ? (
        <p className="py-16 text-center text-sm text-muted-foreground">
          No applications yet — add a job to get started.
        </p>
      ) : (
        <Tabs defaultValue="board">
          <TabsList className="mb-4">
            <TabsTrigger value="board">Board</TabsTrigger>
            <TabsTrigger value="table">Table</TabsTrigger>
          </TabsList>

          <TabsContent value="board">
            <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
              <div className="flex gap-3 overflow-x-auto pb-4">
                {APPLICATION_STAGES.map((stage) => (
                  <BoardColumn
                    key={stage}
                    stage={stage}
                    applications={applications.filter((a) => a.stage === stage)}
                  />
                ))}
              </div>
            </DndContext>
          </TabsContent>

          <TabsContent value="table">
            <div className="mb-3 flex items-center gap-2">
              <label className="text-sm text-muted-foreground">Filter by stage:</label>
              <select
                className="rounded-md border bg-background px-2 py-1 text-sm"
                value={stageFilter}
                onChange={(e) => setStageFilter(e.target.value as ApplicationStage | "all")}
              >
                <option value="all">All stages</option>
                {APPLICATION_STAGES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Company</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>Last activity</TableHead>
                    <TableHead>Next action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredForTable.map((a) => (
                    <TableRow
                      key={a.id}
                      className="cursor-pointer"
                      onClick={() => router.push(`/jobs/${a.job_id}`)}
                    >
                      <TableCell className="font-medium">{a.company}</TableCell>
                      <TableCell>{a.title}</TableCell>
                      <TableCell>
                        <Badge variant={stageBadgeVariant(a.stage)}>{a.stage}</Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDistanceToNow(new Date(a.last_activity_at), { addSuffix: true })}
                      </TableCell>
                      <TableCell className="text-sm">{a.next_action || "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
