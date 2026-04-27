"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, FileText, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { InterviewSidebar } from "@/components/interview-sidebar";
import { uploadResume, getResumes, reuseResume, getProviders } from "@/lib/api";
import { AlertTriangle } from "lucide-react";

interface ResumeItem {
  path: string;
  name: string;
  size: number;
  modified: number;
}

export default function HomePage() {
  const router = useRouter();
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [reusingPath, setReusingPath] = useState("");
  const [error, setError] = useState("");
  const [fileName, setFileName] = useState("");
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [hasApiKey, setHasApiKey] = useState(true);
  const [providerName, setProviderName] = useState("");

  useEffect(() => {
    getResumes()
      .then((res) => setResumes(res.resumes))
      .catch(() => {});
    getProviders()
      .then((res) => {
        setHasApiKey(res.has_api_key);
        const p = res.providers.find((p: { id: string }) => p.id === res.current_provider);
        setProviderName(p?.name || res.current_provider);
      })
      .catch(() => {});
  }, []);

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError("请上传 PDF 格式的简历文件");
        return;
      }
      setFileName(file.name);
      setError("");
      setLoading(true);
      try {
        const { session_id } = await uploadResume(file);
        router.push(`/interview/${session_id}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "上传失败");
        setLoading(false);
      }
    },
    [router]
  );

  const handleReuse = useCallback(
    async (resume: ResumeItem) => {
      setError("");
      setReusingPath(resume.path);
      try {
        const { session_id } = await reuseResume(resume.path);
        router.push(`/interview/${session_id}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "创建会话失败");
        setReusingPath("");
      }
    },
    [router]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const isLoading = loading || !!reusingPath;

  return (
    <div className="flex h-screen">
      <InterviewSidebar phase="upload" />

      <main className="flex flex-1 items-center justify-center p-8">
        <Card className="w-full max-w-lg shadow-lg">
          <CardContent className="p-6">
            {!hasApiKey && (
              <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm dark:border-amber-900 dark:bg-amber-950">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                <div>
                  <p className="font-medium text-amber-800 dark:text-amber-200">
                    未配置 {providerName} API Key
                  </p>
                  <p className="mt-0.5 text-amber-700 dark:text-amber-300">
                    请先点击侧边栏「模型配置」填写 API Key，否则无法解析简历
                  </p>
                </div>
              </div>
            )}

            {/* Existing resumes */}
            {resumes.length > 0 && (
              <>
                <p className="mb-3 text-sm font-medium">选择已有简历</p>
                <div className="space-y-2">
                  {resumes.map((r) => (
                    <button
                      key={r.path}
                      onClick={() => handleReuse(r)}
                      disabled={isLoading}
                      className="flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left text-sm transition-colors hover:bg-accent disabled:opacity-50"
                    >
                      {reusingPath === r.path ? (
                        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                      ) : (
                        <FileText className="h-4 w-4 shrink-0 text-primary" />
                      )}
                      <span className="flex-1 truncate font-medium">{r.name}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {formatSize(r.size)}
                      </span>
                    </button>
                  ))}
                </div>

                <div className="my-4 flex items-center gap-3">
                  <Separator className="flex-1" />
                  <span className="text-xs text-muted-foreground">或上传新简历</span>
                  <Separator className="flex-1" />
                </div>
              </>
            )}

            {/* Upload area */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
                dragging
                  ? "border-primary bg-primary/5"
                  : "border-muted-foreground/20 hover:border-primary/50"
              }`}
            >
              {loading ? (
                <>
                  <Loader2 className="mb-3 h-10 w-10 animate-spin text-primary" />
                  <p className="text-sm font-medium">正在上传...</p>
                  <p className="mt-1 text-xs text-muted-foreground">{fileName}</p>
                </>
              ) : (
                <>
                  <div className="mb-3 rounded-full bg-primary/10 p-3">
                    <Upload className="h-6 w-6 text-primary" />
                  </div>
                  <p className="mb-1 text-sm font-medium">拖拽 PDF 简历到这里</p>
                  <p className="mb-4 text-xs text-muted-foreground">或点击按钮选择文件</p>
                  <Button
                    size="sm"
                    onClick={() => {
                      const input = document.createElement("input");
                      input.type = "file";
                      input.accept = ".pdf";
                      input.onchange = () => {
                        const file = input.files?.[0];
                        if (file) handleFile(file);
                      };
                      input.click();
                    }}
                    disabled={isLoading}
                  >
                    <RefreshCw className="mr-2 h-3.5 w-3.5" />
                    上传新简历
                  </Button>
                </>
              )}
            </div>

            {error && (
              <p className="mt-3 text-center text-sm text-destructive">{error}</p>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
