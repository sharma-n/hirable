"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { useTheme } from "next-themes";
import CodeMirror from "@uiw/react-codemirror";
import { yaml } from "@codemirror/lang-yaml";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  apiCompileDocument,
  apiDraftCoverLetter,
  apiDraftCv,
  apiGetDocument,
  apiListDocuments,
  apiSaveDocument,
  CompileFailure,
  type DocumentDetail,
  type DocumentListItem,
} from "@/lib/api";

export interface DocumentArtifactHandle {
  /** Called by the parent page when the agent's draft tool_result arrives. */
  refetch: () => void;
}

interface DocumentArtifactProps {
  jobId: string;
  documentType: "cv" | "cover_letter";
  title: string;
  emptyText: string;
  generateLabel: string;
  regenerateLabel: string;
  highlighted?: boolean;
}

const STAGE_LABELS: Record<string, string> = {
  yaml: "YAML syntax error",
  schema: "Invalid document data",
  render: "Render failed",
};

export const DocumentArtifact = forwardRef<DocumentArtifactHandle, DocumentArtifactProps>(
  function DocumentArtifact(
    { jobId, documentType, title, emptyText, generateLabel, regenerateLabel, highlighted },
    ref,
  ) {
    const { resolvedTheme } = useTheme();
    const [versions, setVersions] = useState<DocumentListItem[] | "loading">("loading");
    const [current, setCurrent] = useState<DocumentDetail | null>(null);
    const [sourceText, setSourceText] = useState("");
    const [dirty, setDirty] = useState(false);
    const [drafting, setDrafting] = useState(false);
    const [compiling, setCompiling] = useState(false);
    const [saving, setSaving] = useState(false);
    const [compileError, setCompileError] = useState<{ stage: string; errors: string[] } | null>(null);
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const pdfUrlRef = useRef<string | null>(null);

    async function selectVersion(documentId: string) {
      const detail = await apiGetDocument(documentId);
      setCurrent(detail);
      setSourceText(detail.source_text);
      setDirty(false);
      setCompileError(null);
      if (pdfUrlRef.current) {
        URL.revokeObjectURL(pdfUrlRef.current);
        pdfUrlRef.current = null;
        setPdfUrl(null);
      }
    }

    async function loadVersions(preferId?: string) {
      const list = await apiListDocuments(jobId, documentType);
      setVersions(list);
      if (list.length === 0) {
        setCurrent(null);
        setSourceText("");
        return;
      }
      const target = list.find((v) => v.id === preferId) ?? list[0];
      await selectVersion(target.id);
    }

    useEffect(() => {
      loadVersions().catch(() => setVersions([]));
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [jobId, documentType]);

    useEffect(() => {
      return () => {
        if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current);
      };
    }, []);

    useImperativeHandle(ref, () => ({
      refetch: () => {
        loadVersions().catch(() => {
          // non-fatal — the panel just keeps showing whatever it had
        });
      },
    }));

    async function handleGenerate() {
      setDrafting(true);
      try {
        const doc =
          documentType === "cv" ? await apiDraftCv(jobId) : await apiDraftCoverLetter(jobId);
        await loadVersions(doc.id);
        toast.success(`${title} v${doc.version} generated`);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : `Failed to generate ${title.toLowerCase()}`);
      } finally {
        setDrafting(false);
      }
    }

    async function handleCompile() {
      setCompiling(true);
      setCompileError(null);
      try {
        const blob = await apiCompileDocument(sourceText);
        if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current);
        const url = URL.createObjectURL(blob);
        pdfUrlRef.current = url;
        setPdfUrl(url);
      } catch (err) {
        if (err instanceof CompileFailure) {
          setCompileError(err.detail);
        } else {
          toast.error(err instanceof Error ? err.message : "Compile failed");
        }
      } finally {
        setCompiling(false);
      }
    }

    async function handleSave() {
      if (!current) return;
      setSaving(true);
      try {
        const saved = await apiSaveDocument(current.id, sourceText);
        await loadVersions(saved.id);
        toast.success(`Saved as v${saved.version}`);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Save failed");
      } finally {
        setSaving(false);
      }
    }

    return (
      <Card className={highlighted ? "ring-2 ring-primary shadow-md transition-shadow duration-700" : undefined}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <CardTitle className="text-base">{title}</CardTitle>
              {highlighted && (
                <Badge variant="secondary" className="text-[10px]">
                  Updated by agent
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              {versions !== "loading" && versions.length > 0 && (
                <select
                  value={current?.id ?? ""}
                  onChange={(e) => selectVersion(e.target.value)}
                  className="rounded-md border bg-background px-1.5 py-1 text-xs"
                  aria-label="Version"
                >
                  {versions.map((v) => (
                    <option key={v.id} value={v.id}>
                      v{v.version}
                      {v.is_finalized ? " (submitted)" : ""}
                    </option>
                  ))}
                </select>
              )}
              <Button type="button" size="sm" variant="outline" disabled={drafting} onClick={handleGenerate}>
                {drafting ? (
                  <Loader2 className="size-4 animate-spin mr-1.5" />
                ) : (
                  <Sparkles className="size-4 mr-1.5" />
                )}
                {versions === "loading" || versions.length === 0 ? generateLabel : regenerateLabel}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {versions === "loading" ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="size-5 animate-spin text-muted-foreground" />
            </div>
          ) : versions.length === 0 ? (
            <p className="text-sm text-muted-foreground">{emptyText}</p>
          ) : (
            <>
              <div className="rounded-lg border overflow-hidden text-sm">
                <CodeMirror
                  value={sourceText}
                  height="320px"
                  extensions={[yaml()]}
                  theme={resolvedTheme === "dark" ? "dark" : "light"}
                  onChange={(value) => {
                    setSourceText(value);
                    setDirty(value !== current?.source_text);
                  }}
                />
              </div>

              {compileError && (
                <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs space-y-1">
                  <p className="font-medium text-destructive">
                    {STAGE_LABELS[compileError.stage] ?? "Compile error"}
                  </p>
                  {compileError.errors.map((e, i) => (
                    <p key={i} className="text-muted-foreground">
                      {e}
                    </p>
                  ))}
                </div>
              )}

              <div className="flex gap-2">
                <Button type="button" size="sm" variant="outline" disabled={compiling} onClick={handleCompile}>
                  {compiling && <Loader2 className="size-4 animate-spin mr-1.5" />}
                  Compile & preview
                </Button>
                <Button type="button" size="sm" disabled={!dirty || saving} onClick={handleSave}>
                  {saving && <Loader2 className="size-4 animate-spin mr-1.5" />}
                  Save as new version
                </Button>
              </div>

              {pdfUrl && (
                <iframe
                  title={`${title} preview`}
                  src={pdfUrl}
                  className="w-full rounded-lg border"
                  style={{ height: "600px" }}
                />
              )}
            </>
          )}
        </CardContent>
      </Card>
    );
  },
);
