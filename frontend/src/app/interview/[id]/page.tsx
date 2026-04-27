"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Loader2, Mic, MicOff, ChevronDown, FileUser, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { InterviewSidebar } from "@/components/interview-sidebar";
import { ChatMessage } from "@/components/chat-message";
import { CodeEditor } from "@/components/code-editor";
import { ResumePanel, type ResumeData } from "@/components/resume-panel";
import { useInterview } from "@/hooks/use-interview";
import { useVoice } from "@/hooks/use-voice";
import { getJobCategories, getLeetCodeProblem, getProviders, getResumeParsed } from "@/lib/api";

interface LeetCodeProblem {
  id: number;
  title: string;
  difficulty: string;
  description: string;
  code_template: string;
  test_cases: string[];
  slug: string;
  tags: string[];
}

export default function InterviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const {
    phase,
    messages,
    loading,
    error,
    isFinished,
    totalQuestions,
    currentQuestionNum,
    currentQuestion,
    selectJob,
    submitAnswer,
    cancelParse,
  } = useInterview(id);
  const { recording, transcribing, playing, transcript, startRecording, stopRecording, playTTS, stopPlaying } = useVoice();

  const [categories, setCategories] = useState<string[]>([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [includeCoding, setIncludeCoding] = useState(true);
  const [interviewMode, setInterviewMode] = useState<"text" | "voice">("text");
  const [voiceSpeed, setVoiceSpeed] = useState(1.25);
  const [hasVoiceKey, setHasVoiceKey] = useState(true);
  const [input, setInput] = useState("");
  const [leetcodeProblem, setLeetcodeProblem] = useState<LeetCodeProblem | null>(null);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [resumeData, setResumeData] = useState<ResumeData | null>(null);
  const [resumePanelOpen, setResumePanelOpen] = useState(false);
  const [panelWidth, setPanelWidth] = useState(420);
  const isDraggingRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const prevLeetcodeIdRef = useRef<number | null>(null);
  const prevMsgCountRef = useRef(0);

  useEffect(() => {
    if (recording && transcript) {
      setInput(transcript);
    }
  }, [recording, transcript]);

  useEffect(() => {
    getJobCategories().then((res) => {
      setCategories(res.categories);
      if (res.categories.length > 0) setSelectedJob(res.categories[0]);
    });
    getProviders().then((res) => setHasVoiceKey(res.has_voice_key)).catch(() => {});
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (phase === "interview" && !resumeData) {
      getResumeParsed(id).then((data) => setResumeData(data as ResumeData)).catch(() => {});
    }
  }, [phase, id, resumeData]);

  useEffect(() => {
    if (isFinished) router.push(`/report/${id}`);
  }, [isFinished, id, router]);

  useEffect(() => {
    const lcId = currentQuestion?.leetcode_id;
    if (lcId && lcId !== prevLeetcodeIdRef.current) {
      prevLeetcodeIdRef.current = lcId;
      setLeetcodeProblem(null);
      getLeetCodeProblem(lcId).then(setLeetcodeProblem).catch(() => {});
    } else if (!lcId) {
      prevLeetcodeIdRef.current = null;
      setLeetcodeProblem(null);
    }
  }, [currentQuestion]);

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRef.current = true;
    const startX = e.clientX;
    const startWidth = panelWidth;

    const onMouseMove = (ev: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const delta = startX - ev.clientX;
      const newWidth = Math.min(Math.max(startWidth + delta, 280), 700);
      setPanelWidth(newWidth);
    };

    const onMouseUp = () => {
      isDraggingRef.current = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, [panelWidth]);

  // Attach camera stream to video element (only when stream changes)
  const attachCamera = useCallback((el: HTMLVideoElement | null) => {
    videoRef.current = el;
    if (el && cameraStreamRef.current && el.srcObject !== cameraStreamRef.current) {
      el.srcObject = cameraStreamRef.current;
    }
  }, []);

  // Release camera on unmount or when interview finishes
  useEffect(() => {
    return () => {
      cameraStreamRef.current?.getTracks().forEach((t) => t.stop());
      cameraStreamRef.current = null;
    };
  }, []);

  // Auto-play TTS for new interviewer messages in voice mode
  useEffect(() => {
    if (interviewMode !== "voice" || messages.length === 0) return;
    if (messages.length <= prevMsgCountRef.current) {
      prevMsgCountRef.current = messages.length;
      return;
    }
    prevMsgCountRef.current = messages.length;
    const last = messages[messages.length - 1];
    if (last.role === "interviewer") {
      playTTS(last.content, voiceSpeed);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length, interviewMode]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    submitAnswer(text);
  };

  const handleVoiceToggle = useCallback(async () => {
    if (recording) {
      try {
        const text = await stopRecording();
        if (text) {
          setInput(text);
          submitAnswer(text);
        }
      } catch { /* ignore */ }
    } else {
      try {
        if (playing) stopPlaying();
        setInput("");
        await startRecording();
      } catch { /* ignore */ }
    }
  }, [recording, playing, stopRecording, startRecording, stopPlaying, submitAnswer]);

  const handleStartInterview = async () => {
    if (interviewMode === "voice") {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
        // Keep video stream for camera preview, stop audio tracks (re-acquired on recording)
        stream.getAudioTracks().forEach((t) => t.stop());
        cameraStreamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch {
        return;
      }
    }
    selectJob(selectedJob, includeCoding);
  };

  const isCoding = currentQuestion?.leetcode_id != null;

  // Shared chat input bar (used in both chat mode and code mode)
  const chatInputBar = (
    <div className="px-4 py-3">
      <div className="mx-auto max-w-3xl">
        {/* Speed control (voice mode) */}
        {interviewMode === "voice" && (
          <div className="mb-2 flex items-center gap-2">
            <span className="text-xs text-muted-foreground whitespace-nowrap">语速 {voiceSpeed}x</span>
            <input
              type="range"
              min={1.0}
              max={2.0}
              step={0.25}
              value={voiceSpeed}
              onChange={(e) => setVoiceSpeed(parseFloat(e.target.value))}
              className="w-24 accent-primary"
            />
          </div>
        )}
        <div className="flex items-center gap-2 rounded-full border bg-card px-4 py-1.5 shadow-sm focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/10">
          {interviewMode === "voice" && (
            <button
              onClick={handleVoiceToggle}
              disabled={loading || transcribing}
              title={recording ? "停止录音并发送" : "语音输入"}
              className={`shrink-0 rounded-full p-1.5 transition-colors ${
                recording
                  ? "bg-destructive text-destructive-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {transcribing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : recording ? (
                <MicOff className="h-4 w-4" />
              ) : (
                <Mic className="h-4 w-4" />
              )}
            </button>
          )}
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入你的回答或解题思路..."
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/50"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="shrink-0 rounded-full bg-primary p-1.5 text-primary-foreground transition-opacity disabled:opacity-30"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        {recording && (
          <div className="mt-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 animate-pulse rounded-full bg-destructive" />
              <span className="text-xs font-medium text-muted-foreground">实时识别中</span>
            </div>
            {transcript && (
              <p className="mt-1 text-sm text-foreground">{transcript}</p>
            )}
            {!transcript && (
              <p className="mt-1 text-xs text-muted-foreground/60">开始说话...</p>
            )}
          </div>
        )}
        {error && (
          <p className="mt-1 text-sm text-destructive">{error}</p>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex h-screen">
      <InterviewSidebar
        phase={phase}
        progress={{ current_question: currentQuestionNum, total_questions: totalQuestions }}
      />

      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Parsing Resume */}
        {phase === "upload" && (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8">
            {loading ? (
              <>
                <Loader2 className="h-10 w-10 animate-spin text-primary" />
                <div className="text-center">
                  <p className="text-lg font-medium">正在解析简历...</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    AI 正在阅读您的简历，这可能需要 10-30 秒
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={cancelParse}>
                  取消
                </Button>
              </>
            ) : error ? (
              <div className="text-center">
                <p className="text-sm text-destructive">{error}</p>
                <Button variant="outline" size="sm" className="mt-3" onClick={() => window.location.href = "/"}>
                  返回首页
                </Button>
              </div>
            ) : null}
          </div>
        )}

        {/* Job Selection */}
        {phase === "job_select" && (
          <div className="flex flex-1 items-center justify-center p-8">
            <Card className="w-full max-w-md shadow-lg">
              <CardHeader>
                <CardTitle>选择目标岗位</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="space-y-2">
                  <Label>岗位类型</Label>
                  <Select value={selectedJob} onValueChange={(v) => { if (v) setSelectedJob(v); }}>
                    <SelectTrigger>
                      <SelectValue placeholder="选择岗位..." />
                    </SelectTrigger>
                    <SelectContent>
                      {categories.map((c) => (
                        <SelectItem key={c} value={c}>{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={includeCoding}
                    onChange={(e) => setIncludeCoding(e.target.checked)}
                    className="rounded border-gray-300"
                  />
                  包含 LeetCode 算法题
                </label>

                {/* Interview Mode Selection */}
                <div className="space-y-2">
                  <Label>面试模式</Label>
                  <div className="flex gap-3">
                    <button
                      type="button"
                      onClick={() => setInterviewMode("text")}
                      className={`flex-1 rounded-lg border-2 px-4 py-3 text-center text-sm transition-colors ${
                        interviewMode === "text"
                          ? "border-primary bg-primary/5 font-medium text-primary"
                          : "border-muted hover:border-primary/30"
                      }`}
                    >
                      <span className="text-lg">⌨️</span>
                      <p className="mt-1">文本面试</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (!hasVoiceKey) {
                          alert("尚未配置语音 API Key（DashScope），请先在侧边栏「模型配置」中填写");
                          return;
                        }
                        setInterviewMode("voice");
                      }}
                      className={`flex-1 rounded-lg border-2 px-4 py-3 text-center text-sm transition-colors ${
                        interviewMode === "voice"
                          ? "border-primary bg-primary/5 font-medium text-primary"
                          : "border-muted hover:border-primary/30"
                      }`}
                    >
                      <span className="text-lg">🎙️</span>
                      <p className="mt-1">语音面试</p>
                    </button>
                  </div>
                </div>

                {interviewMode === "voice" && (
                  <div className="space-y-2 rounded-lg bg-muted/50 p-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs">语速调整</Label>
                      <span className="text-xs text-muted-foreground">{voiceSpeed}x</span>
                    </div>
                    <input
                      type="range"
                      min={1.0}
                      max={2.0}
                      step={0.25}
                      value={voiceSpeed}
                      onChange={(e) => setVoiceSpeed(parseFloat(e.target.value))}
                      className="w-full accent-primary"
                    />
                    <p className="text-xs text-muted-foreground">
                      语音模式下仍可使用文本输入。点击开始面试时会申请麦克风和摄像头权限。
                    </p>
                  </div>
                )}

                <Button
                  className="w-full"
                  onClick={handleStartInterview}
                  disabled={loading || !selectedJob}
                >
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  {loading ? "正在生成面试题..." : "开始面试"}
                </Button>

                {error && <p className="text-sm text-destructive">{error}</p>}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Chat Mode (no coding question) */}
        {phase === "interview" && !isCoding && (
          <div className="relative flex flex-1 overflow-hidden">
            {/* Main chat area */}
            <div className="flex flex-1 flex-col overflow-hidden">
              {/* Camera preview — fixed top-right, picture-in-picture style */}
              {interviewMode === "voice" && cameraStreamRef.current && (
                <div className="absolute right-4 top-4 z-10">
                  <video
                    ref={attachCamera}
                    autoPlay
                    muted
                    playsInline
                    className="h-32 w-44 rounded-2xl border border-white/20 bg-black object-cover shadow-2xl ring-1 ring-black/5"
                  />
                </div>
              )}

              {/* Resume panel toggle + current entity indicator */}
              <div className="flex h-11 items-center gap-2 border-b px-4">
                <button
                  onClick={() => setResumePanelOpen(!resumePanelOpen)}
                  className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium shadow-sm transition-all ${
                    resumePanelOpen
                      ? "border-primary bg-primary text-primary-foreground shadow-primary/20"
                      : "border-border bg-card text-foreground hover:border-primary/40 hover:shadow-md"
                  }`}
                >
                  <FileUser className="h-4 w-4" />
                  简历概览
                </button>
                {currentQuestion?.related_resume_point && (
                  <span className="rounded-md bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
                    {currentQuestion.related_resume_point}
                  </span>
                )}
              </div>

              <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
                <div className="mx-auto max-w-2xl space-y-4">
                  {/* Collapsible history */}
                  {messages.length > 2 && (
                    <>
                      <button
                        onClick={() => setHistoryExpanded(!historyExpanded)}
                        className="group flex w-full items-center gap-3 py-1"
                      >
                        <div className="h-px flex-1 bg-gradient-to-r from-transparent to-border" />
                        <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground/70 transition-colors group-hover:text-muted-foreground">
                          <ChevronDown className={`h-3 w-3 transition-transform duration-200 ${historyExpanded ? "rotate-180" : ""}`} />
                          {historyExpanded ? "收起" : `${messages.length - 2} 条历史`}
                        </span>
                        <div className="h-px flex-1 bg-gradient-to-l from-transparent to-border" />
                      </button>

                      {historyExpanded && (
                        <div className="space-y-3">
                          {messages.slice(0, -2).map((msg, i) => (
                            <div key={i} className="opacity-40 transition-opacity hover:opacity-70">
                              <ChatMessage role={msg.role} content={msg.content} />
                            </div>
                          ))}
                          <div className="flex items-center gap-3 py-1">
                            <div className="h-px flex-1 bg-gradient-to-r from-transparent to-border/50" />
                            <span className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground/40">当前</span>
                            <div className="h-px flex-1 bg-gradient-to-l from-transparent to-border/50" />
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {/* Latest round — always visible, full opacity */}
                  {messages.slice(-2).map((msg, i) => (
                    <ChatMessage key={`latest-${i}`} role={msg.role} content={msg.content} />
                  ))}

                  {loading && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      面试官思考中...
                    </div>
                  )}
                </div>
              </div>
              {chatInputBar}
            </div>

            {/* Resume panel — raised card style, resizable */}
            <div
              className={`relative flex-shrink-0 ${
                resumePanelOpen ? "" : "w-0 overflow-hidden"
              }`}
              style={resumePanelOpen ? { width: panelWidth } : undefined}
            >
              {resumePanelOpen && (
                <>
                  {/* Drag handle — floats outside the panel */}
                  <div
                    onMouseDown={handleResizeStart}
                    className="group absolute -left-4 top-1/2 z-30 flex h-10 w-4 -translate-y-1/2 cursor-col-resize items-center justify-center rounded-l-md border border-r-0 border-border/60 bg-muted shadow-sm hover:bg-muted-foreground/15 active:bg-primary/20"
                  >
                    <span className="text-[10px] font-bold leading-none text-muted-foreground/50 group-hover:text-muted-foreground group-active:text-primary">»</span>
                  </div>

                  <div className="flex h-full flex-col rounded-l-2xl border border-r-0 border-border/40 bg-card shadow-[-4px_0_16px_rgba(0,0,0,0.06)]">
                    {/* Header */}
                    <div className="flex h-11 items-center gap-2 border-b px-4">
                      <FileUser className="h-4 w-4 text-primary" />
                      <span className="text-sm font-medium">简历概览</span>
                      <button
                        onClick={() => setResumePanelOpen(false)}
                        className="ml-auto rounded-md p-0.5 text-muted-foreground/50 hover:bg-muted hover:text-foreground"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    {/* Content */}
                    <div className="flex-1 overflow-y-auto px-3 py-4">
                      {resumeData ? (
                        <ResumePanel
                          data={resumeData}
                          activeEntity={currentQuestion?.related_resume_point || ""}
                        />
                      ) : (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Code Mode (coding question active) — editor + chat side by side */}
        {phase === "interview" && isCoding && currentQuestion && (
          <div className="flex flex-1 flex-col overflow-hidden">
            <div className="flex flex-1 overflow-hidden">
              {leetcodeProblem ? (
                <CodeEditor
                  sessionId={id}
                  leetcodeId={leetcodeProblem.id}
                  title={leetcodeProblem.title}
                  description={leetcodeProblem.description}
                  codeTemplate={leetcodeProblem.code_template}
                  slug={leetcodeProblem.slug}
                  onSubmit={(code, language) => {
                    const answer = `我的解法（${language}）：\n\`\`\`${language}\n${code}\n\`\`\``;
                    submitAnswer(answer);
                  }}
                  submitting={loading}
                />
              ) : (
                <div className="flex flex-1 items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  <span className="ml-3 text-muted-foreground">加载题目中...</span>
                </div>
              )}
            </div>
            {/* Chat bar below code editor */}
            {chatInputBar}
          </div>
        )}
      </main>
    </div>
  );
}
