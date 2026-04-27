"use client";

import { useCallback, useEffect, useState } from "react";
import { Settings, Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { getProviders, updateConfig } from "@/lib/api";

interface ProviderInfo {
  id: string;
  name: string;
  models: string[];
  default_model: string;
}

export function SettingsDialog() {
  const [open, setOpen] = useState(false);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [currentProvider, setCurrentProvider] = useState("");
  const [currentModel, setCurrentModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [voiceKey, setVoiceKey] = useState("");
  const [hasApiKey, setHasApiKey] = useState(false);
  const [hasVoiceKey, setHasVoiceKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = useCallback(() => {
    getProviders().then((res) => {
      setProviders(res.providers);
      setCurrentProvider(res.current_provider);
      setCurrentModel(res.current_model || "");
      setHasApiKey(res.has_api_key);
      setHasVoiceKey(res.has_voice_key);
    });
  }, []);

  useEffect(() => {
    if (open) {
      load();
      setSaved(false);
      setApiKey("");
      setVoiceKey("");
    }
  }, [open, load]);

  const selectedProvider = providers.find((p) => p.id === currentProvider);
  const models = selectedProvider?.models || [];

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateConfig({
        provider: currentProvider,
        model: currentModel || undefined,
        api_key: apiKey || undefined,
        voice_api_key: voiceKey || undefined,
      });
      setSaved(true);
      setHasApiKey(!!apiKey || hasApiKey);
      setHasVoiceKey(!!voiceKey || hasVoiceKey);
      setApiKey("");
      setVoiceKey("");
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        className="inline-flex w-full items-center justify-start gap-2 rounded-md px-3 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
      >
        <Settings className="h-4 w-4" />
        模型配置
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>模型配置</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {/* Provider */}
          <div className="space-y-2">
            <Label>AI 提供商</Label>
            <Select
              value={currentProvider}
              onValueChange={(v) => {
                if (v) {
                  setCurrentProvider(v);
                  const p = providers.find((x) => x.id === v);
                  setCurrentModel(p?.default_model || "");
                }
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {providers.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Model */}
          {models.length > 0 && (
            <div className="space-y-2">
              <Label>模型</Label>
              <Select
                value={currentModel || selectedProvider?.default_model || ""}
                onValueChange={(v) => { if (v) setCurrentModel(v); }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {models.map((m) => (
                    <SelectItem key={m} value={m}>
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* API Key */}
          <div className="space-y-2">
            <Label>
              {selectedProvider?.name || "LLM"} API Key
              {hasApiKey && (
                <span className="ml-2 text-xs text-green-600">已配置</span>
              )}
            </Label>
            <Input
              type="password"
              placeholder={hasApiKey ? "已配置，留空保持不变" : "输入 API Key..."}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>

          <Separator />

          {/* Voice Key */}
          <div className="space-y-2">
            <Label>
              语音 API Key（通义千问 DashScope）
              {hasVoiceKey && (
                <span className="ml-2 text-xs text-green-600">已配置</span>
              )}
            </Label>
            <Input
              type="password"
              placeholder={hasVoiceKey ? "已配置，留空保持不变" : "可选，用于语音面试"}
              value={voiceKey}
              onChange={(e) => setVoiceKey(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              使用阿里云 DashScope 的 Qwen TTS / STT 服务。
              前往{" "}
              <a
                href="https://dashscope.console.aliyun.com/apiKey"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline"
              >
                dashscope.console.aliyun.com
              </a>
              {" "}获取 API Key。
            </p>
          </div>

          <Button onClick={handleSave} disabled={saving} className="w-full">
            {saving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : saved ? (
              <Check className="mr-2 h-4 w-4" />
            ) : null}
            {saved ? "已保存" : "保存配置"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
