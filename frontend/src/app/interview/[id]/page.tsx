"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Loader2, Mic, MicOff } from "lucide-react";
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
import { useInterview } from "@/hooks/use-interview";
import { useVoice } from "@/hooks/use-voice";
import { getJobCategories, getLeetCodeProblem } from "@/lib/api";

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
  } = useInterview(id);
  const { recording, transcribing, playing, startRecording, stopRecording, playTTS, stopPlaying } = useVoice();

  const [categories, setCategories] = useState<string[]>([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [includeCoding, setIncludeCoding] = useState(true);
  const [interviewMode, setInterviewMode] = useState<"text" | "voice">("text");
  const [voiceSpeed, setVoiceSpeed] = useState(1.25);
  const [input, setInput] = useState("");
  const [leetcodeProblem, setLeetcodeProblem] = useState<LeetCodeProblem | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevLeetcodeIdRef = useRef<number | null>(null);
  const prevMsgCountRef = useRef(0);

  useEffect(() => {
    getJobCategories().then((res) => {
      setCategories(res.categories);
      if (res.categories.length > 0) setSelectedJob(res.categories[0]);
    });
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

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
        if (text) submitAnswer(text);
      } catch { /* ignore */ }
    } else {
      try {
        if (playing) stopPlaying();
        await startRecording();
      } catch { /* ignore */ }
    }
  }, [recording, playing, stopRecording, startRecording, stopPlaying, submitAnswer]);

  const handleStartInterview = async () => {
    if (interviewMode === "voice") {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((t) => t.stop());
      } catch {
        return;
      }
    }
    selectJob(selectedJob, includeCoding);
  };

  const isCoding = currentQuestion?.leetcode_id != null;

  // Shared chat input bar (used in both chat mode and code mode)
  const chatInputBar = (
    <div className="border-t bg-card px-4 py-3">
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
        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入你的回答或解题思路..."
            className="min-h-[40px] resize-none text-sm"
            rows={1}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          {interviewMode === "voice" && (
            <Button
              variant={recording ? "destructive" : "outline"}
              size="icon"
              onClick={handleVoiceToggle}
              disabled={loading || transcribing}
              className="shrink-0"
              title={recording ? "停止录音并发送" : "语音输入"}
            >
              {transcribing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : recording ? (
                <MicOff className="h-4 w-4" />
              ) : (
                <Mic className="h-4 w-4" />
              )}
            </Button>
          )}
          <Button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            size="icon"
            className="shrink-0"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        {recording && (
          <p className="mt-1 text-xs text-destructive animate-pulse">录音中... 点击麦克风按钮停止并发送</p>
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
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <div className="text-center">
              <p className="text-lg font-medium">正在解析简历...</p>
              <p className="mt-1 text-sm text-muted-foreground">
                AI 正在阅读您的简历，这可能需要 10-30 秒
              </p>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
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
                      onClick={() => setInterviewMode("voice")}
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
                      语音模式下仍可使用文本输入。点击开始面试时会申请麦克风权限。
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
          <div className="flex flex-1 flex-col overflow-hidden">
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
              <div className="mx-auto max-w-2xl space-y-4">
                {messages.map((msg, i) => (
                  <ChatMessage key={i} role={msg.role} content={msg.content} />
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
