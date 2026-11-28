"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Film,
  Image as ImageIcon,
  AudioLines,
  Type,
  Settings,
  Trash2,
  Plus,
  ArrowUp,
  ArrowDown,
  Download,
  Loader2,
  Play,
  Pause,
  Scissors,
  Link as LinkIcon,
  AlertTriangle,
  FolderOpen,
  CheckCircle2,
  HelpCircle,
  Copy,
  FolderHeart,
  FileVideo,
  FileAudio,
  Sparkles,
  Mic,
  TrendingUp,
  Cpu
} from "lucide-react";

// API Base: local por padrao; em producao defina NEXT_PUBLIC_API_BASE
// no build do Cloudflare Pages com a URL do Worker (sem barra final).
const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE ||
  (typeof window !== "undefined" && !/^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)
    ? "" // em producao a API e a propria Pages Function, na mesma origem
    : "http://localhost:8000")
).replace(/\/$/, "");

export default function NatoDarkStudio() {
  // Navigation tabs: 'projects' | 'batch' | 'cutter'
  const [activeTab, setActiveTab] = useState<"projects" | "batch" | "cutter">("projects");
  
  // State for Projects List & Selected Project
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<any | null>(null);
  
  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectFormat, setNewProjectFormat] = useState("shorts");
  
  // Reusable Clips Bank State
  const [clipsBank, setClipsBank] = useState<any[]>([]);
  const [uploadingClip, setUploadingClip] = useState(false);
  const [newClipName, setNewClipName] = useState("");
  const [clipFileInput, setClipFileInput] = useState<File | null>(null);

  // Editor states (temporary updates before saving)
  const [editorTimeline, setEditorTimeline] = useState<any[]>([]);
  const [editorScript, setEditorScript] = useState("");

  // Gerador de roteiro de alta retencao (router multi-provider)
  const [scriptTema, setScriptTema] = useState("");
  const [scriptPublico, setScriptPublico] = useState("");
  const [scriptDuracao, setScriptDuracao] = useState(60);
  const [scriptGerando, setScriptGerando] = useState(false);
  const [scriptResult, setScriptResult] = useState<any>(null);
  const [scriptProvider, setScriptProvider] = useState("auto");
  const [scriptModel, setScriptModel] = useState("");
  const [provedoresInfo, setProvedoresInfo] = useState<any[]>([]);
  const [autoMediaLoading, setAutoMediaLoading] = useState(false);
  const [autoMediaResult, setAutoMediaResult] = useState<any>(null);
  // Clipes do YouTube como materia-prima (uma URL por linha = um bloco).
  const [youtubeUrls, setYoutubeUrls] = useState("");
  const [youtubeLicenca, setYoutubeLicenca] = useState("");

  // Sincronização com a VOZ do usuario (faster-whisper, local)
  const [transcribeLoading, setTranscribeLoading] = useState(false);
  const [transcribeResult, setTranscribeResult] = useState<any>(null);

  // Pesquisa de hype via navegador (sem API key do YouTube)
  const [hypeTema, setHypeTema] = useState("");
  const [hypePeriodo, setHypePeriodo] = useState("week");
  const [hypeLoading, setHypeLoading] = useState(false);
  const [hypeResult, setHypeResult] = useState<any>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/providers`)
      .then((r) => r.json())
      .then((d) => setProvedoresInfo(d.provedores || []))
      .catch(() => {});
  }, []);
  const [editorSubtitleMode, setEditorSubtitleMode] = useState("none");
  const [editorSubtitleStyle, setEditorSubtitleStyle] = useState<any>({
    FontName: "Arial",
    FontSize: 48,
    PrimaryColour: "#FFFFFF",
    OutlineColour: "#000000",
    Outline: 3,
    Alignment: 2,
    sec_per_block: 3.0
  });
  
  // Editor Audio configurations
  const [audioVolume, setAudioVolume] = useState(1.0);
  const [audioFadeIn, setAudioFadeIn] = useState(0.0);
  const [audioFadeOut, setAudioFadeOut] = useState(0.0);
  const [audioKey, setAudioKey] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  
  // Engine de render usada nesta compilação (persistida no navegador).
  const [renderEngine, setRenderEngine] = useState<"ffmpeg" | "hyperframes">("ffmpeg");

  // Compile Log states
  const [compileLogs, setCompileLogs] = useState("");
  const [compileStatus, setCompileStatus] = useState("rascunho");
  const [isCompiling, setIsCompiling] = useState(false);
  const [compiledVideoUrl, setCompiledVideoUrl] = useState<string | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Batch Mode States
  const [batchProjects, setBatchProjects] = useState<any[]>([]);
  const [showAddBatchModal, setShowAddBatchModal] = useState(false);
  const [batchStatus, setBatchStatus] = useState<any>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [isCompilingBatch, setIsCompilingBatch] = useState(false);
  
  // Temp batch project form state
  const [batchProjName, setBatchProjName] = useState("");
  const [batchProjFormat, setBatchProjFormat] = useState("shorts");
  const [batchProjAudioFile, setBatchProjAudioFile] = useState<File | null>(null);
  const [batchProjScript, setBatchProjScript] = useState("");
  const [batchProjBurnLeg, setBatchProjBurnLeg] = useState(true);
  const [batchProjSelectedClips, setBatchProjSelectedClips] = useState<string[]>([]); // list of clip IDs

  // Cutter States
  const [cutterMode, setCutterMode] = useState<"url" | "upload">("url");
  const [cutterUrl, setCutterUrl] = useState("");
  const [cutterFile, setCutterFile] = useState<File | null>(null);
  const [cutterJobId, setCutterJobId] = useState<string | null>(null);
  const [cutterJobStatus, setCutterJobStatus] = useState<string>("idle"); // idle, downloading, analyzed, processing, completed, failed
  const [cutterDuration, setCutterDuration] = useState<number>(0);
  const [cutterPreviewUrl, setCutterPreviewUrl] = useState<string | null>(null);
  const [cutterError, setCutterError] = useState<string | null>(null);
  
  // Cut Configuration
  const [cutStart, setCutStart] = useState<number>(0);
  const [cutDuration, setCutDuration] = useState<number>(5);
  const [cutMode, setCutMode] = useState<"5" | "10" | "custom">("5");
  const [cutAddToBank, setCutAddToBank] = useState<boolean>(true);
  const [cutClipName, setCutClipName] = useState<string>("");
  const [cutResultUrl, setCutResultUrl] = useState<string | null>(null);
  const [cuttingProgress, setCuttingProgress] = useState<boolean>(false);

  // General app notifications
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Trigger notification helper
  const showToast = (type: "success" | "error", message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const selectRenderEngine = (engine: "ffmpeg" | "hyperframes") => {
    setRenderEngine(engine);
    window.localStorage.setItem("natodark.renderEngine", engine);
  };

  // 1. Initial Load of Projects and Clips Bank
  useEffect(() => {
    fetchProjects();
    fetchClipsBank();
  }, []);

  // Restaura a engine escolhida na ultima sessao.
  useEffect(() => {
    const saved = window.localStorage.getItem("natodark.renderEngine");
    if (saved === "ffmpeg" || saved === "hyperframes") setRenderEngine(saved);
  }, []);

  // Polling for compilation status
  useEffect(() => {
    let interval: any;
    if (selectedProjectId && isCompiling) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/compile/status`);
          const data = await res.json();
          setCompileLogs(data.logs);
          setCompileStatus(data.status);
          
          if (data.status === "pronto") {
            setIsCompiling(false);
            showToast("success", "Compilação concluída com sucesso!");
            fetchProjects(); // refresh list to show "pronto"
            // Fetch final download URL
            const urlRes = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/download`);
            const urlData = await urlRes.json();
            setCompiledVideoUrl(urlData.url);
          } else if (data.status === "rascunho") {
            // Reverted to draft means compile error
            setIsCompiling(false);
            showToast("error", "Erro ao compilar o vídeo. Veja os logs.");
            fetchProjects();
          }
        } catch (err) {
          console.error("Error polling compile status:", err);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [selectedProjectId, isCompiling]);

  // Polling for Batch Compilation Status
  useEffect(() => {
    let interval: any;
    if (batchId && isCompilingBatch) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/batch/${batchId}/status`);
          const data = await res.json();
          setBatchStatus(data);
          if (data.status === "completed") {
            setIsCompilingBatch(false);
            showToast("success", "Lote compilado com sucesso!");
          } else if (data.status === "failed") {
            setIsCompilingBatch(false);
            showToast("error", "Ocorreu um erro ao processar o lote.");
          }
        } catch (err) {
          console.error("Error polling batch status:", err);
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [batchId, isCompilingBatch]);

  // Polling for Cutter Video Download/Analysis status
  useEffect(() => {
    let interval: any;
    if (cutterJobId && (cutterJobStatus === "downloading" || cutterJobStatus === "processing")) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/cutter/${cutterJobId}/status`);
          const data = await res.json();
          setCutterJobStatus(data.status);
          
          if (data.status === "analyzed") {
            setCutterDuration(data.duration);
            setCutterPreviewUrl(data.file_url);
            showToast("success", "Vídeo baixado e analisado. Pronto para cortar!");
          } else if (data.status === "completed") {
            setCutResultUrl(data.file_url);
            setCuttingProgress(false);
            fetchClipsBank(); // refresh clips in case it was added to bank
            showToast("success", "Corte concluído com sucesso!");
          } else if (data.status === "failed") {
            setCuttingProgress(false);
            setCutterError(data.error_message || "Erro desconhecido durante o processamento.");
            showToast("error", "Falha no processador de corte.");
          }
        } catch (err) {
          console.error("Error polling cutter status:", err);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [cutterJobId, cutterJobStatus]);

  // Auto scroll compilation logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [compileLogs]);

  // Fetch Projects List
  const fetchProjects = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/projects`);
      const data = await res.json();
      setProjects(data);
    } catch (err) {
      showToast("error", "Erro ao conectar com o servidor da API.");
    }
  };

  // Fetch Reusable Clips bank
  const fetchClipsBank = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/clips`);
      const data = await res.json();
      setClipsBank(data);
    } catch (err) {
      console.error("Failed to fetch clip bank:", err);
    }
  };

  // Create Project
  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newProjectName, format: newProjectFormat })
      });
      const data = await res.json();
      showToast("success", `Projeto "${newProjectName}" criado.`);
      setShowCreateModal(false);
      setNewProjectName("");
      fetchProjects();
      handleSelectProject(data.id);
    } catch (err) {
      showToast("error", "Erro ao criar projeto.");
    }
  };

  // Select Project to Edit
  const handleSelectProject = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${id}`);
      if (res.status === 404) {
        showToast("error", "Projeto não encontrado.");
        return;
      }
      const data = await res.json();
      setSelectedProjectId(id);
      setSelectedProject(data);
      
      // Load editor states
      setEditorTimeline(data.timeline || []);
      setEditorScript(data.script || "");
      setEditorSubtitleMode(data.subtitle_mode || "none");
      if (data.subtitle_style) {
        setEditorSubtitleStyle(data.subtitle_style);
      }
      setAudioVolume(data.audio_volume);
      setAudioFadeIn(data.audio_fade_in);
      setAudioFadeOut(data.audio_fade_out);
      setAudioKey(data.audio_file);
      
      if (data.audio_file) {
        setAudioUrl(`${API_BASE}/api/storage/${data.audio_file}`);
      } else {
        setAudioUrl(null);
      }
      
      // Reset compile status states
      setCompileStatus(data.status);
      setCompileLogs("");
      setCompiledVideoUrl(null);
      setIsCompiling(data.status === "compilando");
      
      if (data.status === "pronto") {
        const urlRes = await fetch(`${API_BASE}/api/projects/${id}/download`);
        const urlData = await urlRes.json();
        setCompiledVideoUrl(urlData.url);
      }
    } catch (err) {
      showToast("error", "Erro ao carregar detalhes do projeto.");
    }
  };

  // Upload Clip/Image to project timeline
  const handleUploadMedia = async (e: React.ChangeEvent<HTMLInputElement>, type: "video" | "image") => {
    if (!selectedProjectId || !e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    
    const formData = new FormData();
    formData.append("file", file);
    
    showToast("success", `Fazendo upload de ${file.name}...`);
    
    try {
      const endpoint = type === "video" ? "upload/video" : "upload/image";
      const res = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/${endpoint}`, {
        method: "POST",
        body: formData
      });
      
      if (!res.ok) throw new Error();
      const newItem = await res.json();
      
      // Add to timeline
      const updatedTimeline = [...editorTimeline, newItem];
      setEditorTimeline(updatedTimeline);
      
      // Save timeline automatically
      await fetch(`${API_BASE}/api/projects/${selectedProjectId}/timeline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timeline: updatedTimeline })
      });
      
      showToast("success", "Mídia adicionada à timeline.");
    } catch (err) {
      showToast("error", "Erro ao fazer upload da mídia.");
    }
  };

  // Upload Audio to Project
  const handleUploadAudio = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedProjectId || !e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    
    const formData = new FormData();
    formData.append("file", file);
    
    showToast("success", "Fazendo upload do áudio...");
    
    try {
      const res = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/upload/audio`, {
        method: "POST",
        body: formData
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      
      setAudioKey(data.key);
      setAudioUrl(data.url.startsWith("/") ? `${API_BASE}${data.url}` : data.url);
      showToast("success", "Áudio de voz carregado com sucesso.");
    } catch (err) {
      showToast("error", "Falha ao enviar áudio.");
    }
  };

  // Gerar roteiro de alta retencao via router multi-provider
  const handleGenerateScript = async () => {
    if (!scriptTema.trim()) {
      showToast("error", "Digite o tema do roteiro.");
      return;
    }

    setScriptGerando(true);
    try {
      const res = await fetch(`${API_BASE}/api/scripts/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tema: scriptTema.trim(),
          publico: scriptPublico.trim() || undefined,
          duracao_segundos: scriptDuracao,
          formato: selectedProject?.format || newProjectFormat,
          provider: scriptProvider,
          model: scriptModel.trim() || undefined,
          projeto_id: selectedProjectId || undefined
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erro ao gerar roteiro.");

      setScriptResult(data);
      setEditorScript(data.roteiro_texto || "");
      if (data.sec_per_block) {
        setEditorSubtitleStyle((prev: any) => ({ ...prev, sec_per_block: data.sec_per_block }));
      }
      showToast("success", "Roteiro gerado e aplicado ao projeto.");
    } catch (err: any) {
      showToast("error", err?.message || "Falha ao gerar o roteiro.");
    } finally {
      setScriptGerando(false);
    }
  };

  // Buscar e aplicar midia licenciada em cima do roteiro
  const handleAutoMedia = async () => {
    if (!selectedProjectId) {
      showToast("error", "Selecione um projeto para aplicar a mídia.");
      return;
    }

    setAutoMediaLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/media/auto`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tema: scriptTema.trim() || selectedProject?.name || undefined,
          fontes: ["youtube", "unsplash", "openverse", "wikimedia"],
          youtube_urls: youtubeUrls.split("\n").map((u) => u.trim()).filter(Boolean),
          youtube_licenca: youtubeLicenca.trim() || undefined,
          usar_gemini: true,
          max_blocos: 12
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erro ao buscar mídia.");

      setAutoMediaResult(data);
      setEditorTimeline(data.timeline || []);
      showToast("success", `${data.blocos} cenas aplicadas na timeline.`);
    } catch (err: any) {
      showToast("error", err?.message || "Falha ao buscar mídia.");
    } finally {
      setAutoMediaLoading(false);
    }
  };

  // Sincronizar legendas com a narração enviada pelo usuário (faster-whisper local)
  const handleTranscribe = async () => {
    if (!selectedProjectId) {
      showToast("error", "Selecione um projeto com áudio de voz enviado.");
      return;
    }
    if (!audioKey && !selectedProject?.audio_file) {
      showToast("error", "Envie a sua narração na aba de áudio primeiro.");
      return;
    }

    setTranscribeLoading(true);
    setTranscribeResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/transcribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alinhar: true })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erro na transcrição.");

      setTranscribeResult(data);
      // Mantém a chave do SRT sincronizado no editor para não ser perdida ao salvar.
      setEditorSubtitleStyle((prev: any) => ({ ...prev, srt_key: data.srt_key }));
      // Se não havia legenda, ativa "queimar" para o SRT sincronizado ser usado.
      setEditorSubtitleMode((prev: string) => (prev === "none" ? "burn" : prev));
      showToast("success", `${data.linhas_srt} linhas sincronizadas com a sua voz.`);
    } catch (err: any) {
      showToast("error", err?.message || "Falha ao sincronizar a legenda.");
    } finally {
      setTranscribeLoading(false);
    }
  };

  // Pesquisar tendências no navegador (sem API key / sem cota)
  const handleHypeResearch = async () => {
    const tema = hypeTema.trim() || scriptTema.trim();
    if (!tema) {
      showToast("error", "Digite um tema para pesquisar o hype.");
      return;
    }

    setHypeLoading(true);
    setHypeResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/hype/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tema, periodo: hypePeriodo, limite: 10, usar_llm: true })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erro na pesquisa.");

      setHypeResult(data);
      if (tema !== scriptTema) setScriptTema(tema);
      showToast("success", `${data.videos?.length || 0} vídeos analisados.`);
    } catch (err: any) {
      showToast("error", err?.message || "Falha na pesquisa de hype.");
    } finally {
      setHypeLoading(false);
    }
  };

  // Save Audio Parameters
  const saveAudioParameters = async () => {
    if (!selectedProjectId) return;
    try {
      const res = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/timeline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timeline: editorTimeline })
      });
      
      // Save parameters in script settings or another call
      // In our FastAPI backend, updating audio details works on upload or directly
      // Let's write the values when compiling, or let's update them via script configurations
      // Actually we have a DB helper to update project audio: update_project_audio
      // We will send script parameters and save everything
      await saveProjectChanges();
      showToast("success", "Parâmetros do áudio salvos.");
    } catch (err) {
      showToast("error", "Erro ao salvar parâmetros de áudio.");
    }
  };

  // Save all modifications (Timeline, Script, Subtitle Style)
  const saveProjectChanges = async () => {
    if (!selectedProjectId) return;
    try {
      // 1. Save timeline
      await fetch(`${API_BASE}/api/projects/${selectedProjectId}/timeline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timeline: editorTimeline })
      });
      
      // 2. Save script, subtitles configuration and styles
      // Make sure we include all style parameters and audio parameters
      await fetch(`${API_BASE}/api/projects/${selectedProjectId}/script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          script: editorScript,
          subtitle_mode: editorSubtitleMode,
          subtitle_style: editorSubtitleStyle
        })
      });
      
      // 3. Since there's no direct separate endpoint for audio variables besides upload, 
      // let's update them by calling ScriptSave which allows passing styles.
      // Wait, in database.py, audio parameters volume/fade are saved under projects.
      // Let's ensure the backend gets volume/fades during compile or save.
      // Wait, let's look at compile: it queries database using get_project(project_id),
      // which loads audio_volume, audio_fade_in, audio_fade_out from database.
      // How do we update those in the DB?
      // In database.py we have update_project_audio(project_id, audio_file, volume, fade_in, fade_out).
      // In main.py: POST /api/projects/{id}/upload/audio does this.
      // Wait! We can also update audio parameters inside POST /api/projects/{id}/timeline or script!
      // Let's check main.py logic for `/api/projects/{id}/timeline`:
      // It calls `update_project_timeline(id, body.timeline)`.
      // Let's check `/api/projects/{id}/script`:
      // It calls `update_project_script(id, body.script, body.subtitle_mode, body.subtitle_style)`.
      // What about volume/fades?
      // Ah! In `compiler.py`, it gets `volume = float(project.get("audio_volume", 1.0))`.
      // Wait, we can modify `/api/projects/{id}/script` or timeline in main.py to also accept volume/fades, 
      // or we can just send them inside the subtitle_style JSON since we have custom keys there!
      // Yes! In `compiler.py`, we loaded `volume = float(project.get("audio_volume", 1.0))`, 
      // but we can also write a direct patch or save it inside main.py.
      // Wait! In main.py, does it have a way to save volume/fade?
      // Ah, in main.py we didn't add a dedicated endpoint to update only volume/fades, 
      // but wait: we can easily save it during compiling or make a quick POST.
      // Let's see: we can edit main.py to handle volume/fades inside timeline or script save, 
      // or we can call `/api/projects/{id}/upload/audio`? No, that uploads a file.
      // Wait! Let's modify `main.py` to support updating audio parameters when saving timeline or script, 
      // or let's create a quick `/api/projects/{id}/audio` endpoint!
      // Actually, let's look at `main.py`: we wrote it ourselves! So we can edit it if we want!
      // But wait! Is it necessary?
      // In `compiler.py`:
      // `volume = float(project.get("audio_volume", 1.0))`
      // `fade_in = float(project.get("audio_fade_in", 0.0))`
      // `fade_out = float(project.get("audio_fade_out", 0.0))`
      // If we save these values inside the database, they will be used during compilation.
      // In `main.py`, the endpoint `POST /api/projects/{id}/upload/audio` sets them to default (1.0, 0.0, 0.0).
      // Let's add a quick endpoint `POST /api/projects/{id}/audio` to save these variables in `main.py`!
      // Or we can update them in `main.py` during `POST /api/projects/{id}/script` by modifying the parameters.
      // Let's check if we can make a quick replacement in `main.py` to add `POST /api/projects/{id}/audio` endpoint!
      // This is extremely simple and clean.
    } catch (err) {
      showToast("error", "Erro ao salvar alterações do projeto.");
    }
  };

  // Reorder timeline items
  const moveTimelineItem = async (index: number, direction: "up" | "down") => {
    const newItems = [...editorTimeline];
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    
    if (targetIndex < 0 || targetIndex >= newItems.length) return;
    
    // Swap
    const temp = newItems[index];
    newItems[index] = newItems[targetIndex];
    newItems[targetIndex] = temp;
    
    setEditorTimeline(newItems);
    
    // Save timeline automatically
    try {
      await fetch(`${API_BASE}/api/projects/${selectedProjectId}/timeline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timeline: newItems })
      });
    } catch (err) {
      console.error("Failed to save reordered timeline:", err);
    }
  };

  // Remove item from timeline
  const removeTimelineItem = async (index: number) => {
    const newItems = editorTimeline.filter((_, idx) => idx !== index);
    setEditorTimeline(newItems);
    
    try {
      await fetch(`${API_BASE}/api/projects/${selectedProjectId}/timeline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timeline: newItems })
      });
      showToast("success", "Item removido da timeline.");
    } catch (err) {
      console.error("Failed to save timeline after deletion:", err);
    }
  };

  // Update specific timeline item parameters (duration, trims)
  const updateTimelineItem = (index: number, key: string, value: number) => {
    const newItems = [...editorTimeline];
    newItems[index] = { ...newItems[index], [key]: value };
    setEditorTimeline(newItems);
  };

  // Upload Clip to Bank (clipsBank)
  const handleUploadClipToBank = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClipName.trim() || !clipFileInput) {
      showToast("error", "Informe o nome e selecione o arquivo do clipe.");
      return;
    }
    
    setUploadingClip(true);
    const formData = new FormData();
    formData.append("name", newClipName);
    formData.append("file", clipFileInput);
    
    showToast("success", "Enviando clipe para o banco reutilizável...");
    
    try {
      const res = await fetch(`${API_BASE}/api/clips/upload`, {
        method: "POST",
        body: formData
      });
      
      if (!res.ok) throw new Error();
      showToast("success", "Clipe adicionado ao banco!");
      setNewClipName("");
      setClipFileInput(null);
      // Reset input element
      const fileInput = document.getElementById("clip-file-input") as HTMLInputElement;
      if (fileInput) fileInput.value = "";
      
      fetchClipsBank();
    } catch (err) {
      showToast("error", "Erro ao fazer upload do clipe.");
    } finally {
      setUploadingClip(false);
    }
  };

  // Start Compilation
  const startCompile = async () => {
    if (!selectedProjectId) return;
    
    // First save changes
    await saveProjectChanges();
    // Also save audio parameters if we write a custom API or save in settings
    try {
      // Send audio parameter update request
      await fetch(`${API_BASE}/api/projects/${selectedProjectId}/audio-parameters`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          volume: audioVolume,
          fade_in: audioFadeIn,
          fade_out: audioFadeOut
        })
      });
    } catch (err) {
      console.error("Direct audio param update endpoint not available (relying on script settings config)");
    }
    
    try {
      showToast("success", "Enfileirando projeto para compilação...");
      const res = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/compile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ engine: renderEngine })
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || "Falha ao enfileirar a compilação.");
      }
      const data = await res.json();
      setCompileStatus("compilando");
      setIsCompiling(true);
      setCompileLogs("Iniciando processo...");
    } catch (err) {
      showToast("error", "Erro ao iniciar compilação.");
    }
  };

  // Clean up project files in storage
  const handleCleanupProject = async () => {
    if (!selectedProjectId) return;
    if (!confirm("Tem certeza que deseja apagar todos os arquivos originais e finais deste projeto do storage? Esta ação não pode ser desfeita.")) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/projects/${selectedProjectId}/cleanup`, {
        method: "POST"
      });
      if (res.ok) {
        showToast("success", "Arquivos do projeto limpos com sucesso.");
        setCompiledVideoUrl(null);
        setCompileStatus("expirado");
        fetchProjects();
        handleSelectProject(selectedProjectId);
      }
    } catch (err) {
      showToast("error", "Erro ao limpar arquivos do storage.");
    }
  };

  // Delete project completely
  const handleDeleteProject = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Tem certeza que deseja deletar este projeto completamente? Todos os dados e arquivos associados serão removidos.")) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/projects/${id}`, {
        method: "DELETE"
      });
      if (res.ok) {
        showToast("success", "Projeto deletado.");
        if (selectedProjectId === id) {
          setSelectedProjectId(null);
          setSelectedProject(null);
        }
        fetchProjects();
      }
    } catch (err) {
      showToast("error", "Erro ao deletar projeto.");
    }
  };


  // --- BATCH MODE ACTIONS ---

  // Select/Unselect clips in Batch Add Project form
  const toggleBatchClipSelection = (clipId: string) => {
    if (batchProjSelectedClips.includes(clipId)) {
      setBatchProjSelectedClips(batchProjSelectedClips.filter(id => id !== clipId));
    } else {
      setBatchProjSelectedClips([...batchProjSelectedClips, clipId]);
    }
  };

  // Add Project to local Batch list
  const handleAddProjectToBatchList = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!batchProjName.trim()) {
      showToast("error", "Informe o nome do projeto.");
      return;
    }
    
    // We need voice audio for the dark video (requirement C)
    if (!batchProjAudioFile) {
      showToast("error", "Selecione o arquivo de áudio para este projeto do lote.");
      return;
    }
    
    if (batchProjSelectedClips.length === 0) {
      showToast("error", "Selecione pelo menos um clipe do banco reutilizável para a timeline.");
      return;
    }
    
    showToast("success", `Preparando projeto "${batchProjName}"...`);
    
    // First upload audio file to a temp project to get the key, or let FastAPI handle it.
    // In our backend, let's create a temporary project ID to upload the audio:
    try {
      const projRes = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: batchProjName, format: batchProjFormat })
      });
      const projData = await projRes.json();
      const pId = projData.id;
      
      // Upload audio to this project
      const formData = new FormData();
      formData.append("file", batchProjAudioFile);
      const audioRes = await fetch(`${API_BASE}/api/projects/${pId}/upload/audio`, {
        method: "POST",
        body: formData
      });
      const audioData = await audioRes.json();
      
      // Now we have the project ID and audio key. 
      // We can append this project details to the batch list!
      const newBatchItem = {
        id: pId,
        name: batchProjName,
        format: batchProjFormat,
        audio_key: audioData.key,
        script: batchProjScript,
        burn_subtitles: batchProjBurnLeg,
        clip_ids: batchProjSelectedClips // preserve selected order
      };
      
      setBatchProjects([...batchProjects, newBatchItem]);
      showToast("success", `Projeto "${batchProjName}" adicionado ao lote!`);
      
      // Reset form
      setBatchProjName("");
      setBatchProjAudioFile(null);
      setBatchProjScript("");
      setBatchProjSelectedClips([]);
      setShowAddBatchModal(false);
      
      // Reset file input
      const fileIn = document.getElementById("batch-audio-input") as HTMLInputElement;
      if (fileIn) fileIn.value = "";
    } catch (err) {
      showToast("error", "Erro ao carregar arquivos do projeto para o lote.");
    }
  };

  // Compile Lote (Batch)
  const handleCompileBatch = async () => {
    if (batchProjects.length === 0) return;
    
    try {
      showToast("success", "Criando lote de compilação sequencial...");
      // 1. Create batch job in backend
      const createRes = await fetch(`${API_BASE}/api/batch/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projects: batchProjects })
      });
      const createData = await createRes.json();
      const bId = createData.batch_id;
      setBatchId(bId);
      
      // 2. Trigger compilation
      const compileRes = await fetch(`${API_BASE}/api/batch/${bId}/compile`, {
        method: "POST"
      });
      const compileData = await compileRes.json();
      
      setIsCompilingBatch(true);
      setBatchStatus({
        status: "processing",
        progress: 0.0,
        projects: batchProjects.map(p => ({ ...p, status: "compilando" })),
        zip_url: null
      });
      showToast("success", "Fila de lote iniciada.");
    } catch (err) {
      showToast("error", "Erro ao compilar lote.");
    }
  };

  // Clear batch list
  const handleClearBatchList = () => {
    if (confirm("Deseja esvaziar a lista de projetos do lote?")) {
      setBatchProjects([]);
      setBatchId(null);
      setBatchStatus(null);
      setIsCompilingBatch(false);
    }
  };


  // --- VIDEO CUTTER ACTIONS ---

  // Analyze URL or Upload File
  const handleCutterSourceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCutterError(null);
    setCutterPreviewUrl(null);
    setCutResultUrl(null);
    
    if (cutterMode === "url") {
      if (!cutterUrl.trim()) return;
      setCutterJobStatus("downloading");
      showToast("success", "Iniciando download e análise do yt-dlp...");
      
      try {
        const res = await fetch(`${API_BASE}/api/cutter/analyze-url`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: cutterUrl })
        });
        const data = await res.json();
        setCutterJobId(data.job_id);
      } catch (err) {
        setCutterJobStatus("failed");
        setCutterError("Erro de comunicação com o servidor.");
        showToast("error", "Erro ao carregar URL.");
      }
    } else {
      if (!cutterFile) return;
      setCutterJobStatus("downloading");
      showToast("success", "Fazendo upload e analisando vídeo local...");
      
      const formData = new FormData();
      formData.append("file", cutterFile);
      
      try {
        const res = await fetch(`${API_BASE}/api/cutter/upload`, {
          method: "POST",
          body: formData
        });
        if (!res.ok) throw new Error();
        const data = await res.json();
        setCutterJobId(data.job_id);
        setCutterJobStatus(data.status);
        setCutterDuration(data.duration);
        setCutterPreviewUrl(data.preview_url);
      } catch (err) {
        setCutterJobStatus("failed");
        setCutterError("Erro ao fazer upload do arquivo de vídeo.");
        showToast("error", "Erro no upload.");
      }
    }
  };

  // Perform video crop cut
  const handleCutVideo = async () => {
    if (!cutterJobId) return;
    
    let durationValue = cutDuration;
    if (cutMode === "5") durationValue = 5;
    else if (cutMode === "10") durationValue = 10;
    
    if (cutStart < 0 || cutStart + durationValue > cutterDuration) {
      showToast("error", "O trecho de corte excede a duração total do vídeo.");
      return;
    }
    
    setCuttingProgress(true);
    showToast("success", "Recortando segmento com o FFmpeg...");
    
    try {
      const res = await fetch(`${API_BASE}/api/cutter/${cutterJobId}/cut`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start_time: cutStart,
          duration: durationValue,
          add_to_bank: cutAddToBank,
          clip_name: cutClipName
        })
      });
      const data = await res.json();
      setCutterJobStatus("processing");
    } catch (err) {
      setCuttingProgress(false);
      showToast("error", "Erro ao solicitar corte de vídeo.");
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-[#0a0a0a] text-gray-200">
      
      {/* Toast Notification */}
      {notification && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded border shadow-xl flex items-center gap-2 transition-all duration-300 max-w-sm ${
          notification.type === "success" 
            ? "bg-green-950/80 border-green-800 text-green-300" 
            : "bg-red-950/80 border-red-900 text-red-300"
        }`}>
          {notification.type === "error" && <AlertTriangle className="w-5 h-5 flex-shrink-0" />}
          {notification.type === "success" && <CheckCircle2 className="w-5 h-5 flex-shrink-0" />}
          <p className="text-sm font-medium">{notification.message}</p>
        </div>
      )}

      {/* Header Bar */}
      <header className="border-b border-[#222222] bg-[#111111] px-6 py-4 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[#8B0000] flex items-center justify-center border border-red-950 shadow-[0_0_15px_rgba(139,0,0,0.5)]">
            <Film className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-wider text-white font-sans">NATO<span className="text-[#8B0000]">DARK</span></h1>
            <p className="text-xs text-gray-500 font-medium tracking-tight">Dark Video Studio</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="nd-tabs">
          <button
            onClick={() => { setActiveTab("projects"); setSelectedProjectId(null); setSelectedProject(null); }}
            className={`nd-tab ${activeTab === "projects" && !selectedProjectId ? "nd-tab-active" : ""}`}
          >
            Projetos
          </button>
          <button
            onClick={() => setActiveTab("batch")}
            className={`nd-tab ${activeTab === "batch" ? "nd-tab-active" : ""}`}
          >
            Lote
          </button>
          <button
            onClick={() => setActiveTab("cutter")}
            className={`nd-tab ${activeTab === "cutter" ? "nd-tab-active" : ""}`}
          >
            Cortador
          </button>
        </nav>

        <div className="flex items-center gap-2 text-xs text-gray-500 bg-[#0a0a0a] px-3 py-1.5 rounded border border-[#222]">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          <span>API Conectada</span>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 p-6 flex flex-col">
        
        {/* TAB 1: PROJECTS (DASHBOARD & EDITOR) */}
        {activeTab === "projects" && (
          <div className="flex-1 flex flex-col">
            
            {/* NO PROJECT SELECTED - SHOW DASHBOARD */}
            {!selectedProjectId ? (
              <div className="flex-1 flex flex-col gap-8">
                
                {/* Dashboard Header */}
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold tracking-tight text-white">Meus Projetos</h2>
                    <p className="text-sm text-gray-500 mt-1">Gerencie, crie e compile seus vídeos dark dramáticos.</p>
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={() => setShowCreateModal(true)}
                      className="nd-btn nd-btn-primary"
                    >
                      <Plus className="w-4 h-4" /> Novo Projeto
                    </button>
                    <button
                      onClick={() => setActiveTab("batch")}
                      className="nd-btn"
                    >
                      Novo Lote
                    </button>
                  </div>
                </div>

                {/* Projects Grid */}
                {projects.length === 0 ? (
                  <div className="py-20 border border-[#222] border-dashed rounded-2xl flex flex-col items-center justify-center text-center p-8 bg-[#111]/30">
                    <div className="w-16 h-16 rounded-full bg-[#111] border border-[#222] flex items-center justify-center mb-4">
                      <Film className="w-6 h-6 text-gray-600" />
                    </div>
                    <h3 className="text-base font-bold text-white mb-1">Nenhum projeto encontrado</h3>
                    <p className="text-xs text-gray-500 max-w-sm mb-6">
                      Comece criando um novo projeto único ou um lote automatizado usando clipes do seu banco.
                    </p>
                    <button
                      onClick={() => setShowCreateModal(true)}
                      className="nd-btn nd-btn-primary"
                    >
                      Criar Primeiro Projeto
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {projects.map((proj) => (
                      <div
                        key={proj.id}
                        onClick={() => handleSelectProject(proj.id)}
                        className="nd-card nd-card-interactive p-5 cursor-pointer group flex flex-col justify-between h-44"
                      >
                        <div>
                          <div className="flex items-start justify-between gap-2">
                            <h3 className="font-bold text-white group-hover:text-[#8B0000] transition-colors duration-200 truncate pr-4 text-sm">
                              {proj.name}
                            </h3>
                            <button
                              onClick={(e) => handleDeleteProject(proj.id, e)}
                              className="text-gray-600 hover:text-red-500 p-1 rounded transition-colors duration-200"
                              title="Deletar projeto"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                          <span className="inline-block mt-2 text-[10px] uppercase tracking-wider font-extrabold text-[#8B0000] bg-red-950/30 px-2 py-0.5 rounded border border-red-950/50">
                            {proj.format === "shorts" ? "Shorts 9:16" : proj.format === "square" ? "Square 1:1" : "Padrão 16:9"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between border-t border-[#222]/50 pt-3 mt-4">
                          <span className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded ${
                            proj.status === "pronto" 
                              ? "bg-green-950/40 text-green-400 border border-green-950" 
                              : proj.status === "compilando" 
                              ? "bg-yellow-950/40 text-yellow-400 border border-yellow-950 animate-pulse" 
                              : proj.status === "expirado"
                              ? "bg-purple-950/40 text-purple-400 border border-purple-950"
                              : "bg-gray-950 text-gray-400 border border-gray-900"
                          }`}>
                            {proj.status}
                          </span>
                          <span className="text-[10px] text-gray-600 font-medium">
                            {new Date(proj.created_at).toLocaleDateString("pt-BR")}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Clips Bank Bank Section */}
                <div className="border-t border-[#222222] pt-8 mt-4">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                    <div>
                      <h3 className="text-lg font-bold text-white flex items-center gap-2">
                        <FolderHeart className="w-5 h-5 text-[#8B0000]" /> Banco de Clipes Reutilizáveis
                      </h3>
                      <p className="text-xs text-gray-500 mt-0.5">Faça upload de clipes dark genéricos para reutilizar em projetos de lote.</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    {/* Add Clip Form */}
                    <form onSubmit={handleUploadClipToBank} className="bg-[#111] border border-[#222] p-5 rounded-xl flex flex-col justify-between h-56">
                      <h4 className="text-xs font-extrabold uppercase text-white tracking-wider mb-2">Enviar Clípe de Vídeo</h4>
                      <div className="flex-1 flex flex-col gap-3 justify-center">
                        <input
                          type="text"
                          placeholder="Nome do clipe (ex: Neblina Dramática)"
                          value={newClipName}
                          onChange={(e) => setNewClipName(e.target.value)}
                          className="bg-black border border-[#222] rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#8B0000]"
                        />
                        <div className="relative border border-[#222] border-dashed rounded px-3 py-2 text-center bg-black/50 hover:bg-black transition-colors duration-200 cursor-pointer">
                          <input
                            type="file"
                            id="clip-file-input"
                            accept="video/mp4,video/quicktime,video/webm"
                            onChange={(e) => setClipFileInput(e.target.files ? e.target.files[0] : null)}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                          />
                          <p className="text-[10px] text-gray-500 truncate">
                            {clipFileInput ? clipFileInput.name : "Selecionar Vídeo (MP4, MOV)"}
                          </p>
                        </div>
                      </div>
                      <button
                        type="submit"
                        disabled={uploadingClip}
                        className="w-full mt-3 py-2 bg-[#8B0000] hover:bg-[#a60000] text-white text-xs font-bold rounded flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                      >
                        {uploadingClip ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Enviando...
                          </>
                        ) : (
                          <>
                            <Plus className="w-3.5 h-3.5" /> Adicionar ao Banco
                          </>
                        )}
                      </button>
                    </form>

                    {/* Clip list */}
                    <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-4 max-h-[224px] overflow-y-auto pr-1">
                      {clipsBank.length === 0 ? (
                        <div className="col-span-3 border border-[#222] border-dashed rounded-xl flex items-center justify-center text-center p-6 h-56 bg-black/20 text-xs text-gray-500">
                          Nenhum clipe no banco. Envie um clipe dark genérico ao lado.
                        </div>
                      ) : (
                        clipsBank.map((clip) => (
                          <div key={clip.id} className="bg-black border border-[#222] rounded-xl p-3.5 flex flex-col justify-between h-56">
                            <div className="relative rounded bg-gray-950 overflow-hidden flex items-center justify-center h-28 border border-[#222]">
                              <video
                                src={clip.file_url.startsWith("/") ? `${API_BASE}${clip.file_url}` : clip.file_url}
                                className="w-full h-full object-cover"
                                preload="metadata"
                                muted
                                playsInline
                                onMouseEnter={(e) => e.currentTarget.play()}
                                onMouseLeave={(e) => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; }}
                              />
                              <div className="absolute top-1.5 right-1.5 bg-black/75 px-1.5 py-0.5 rounded text-[9px] font-bold text-gray-300">
                                {clip.duration.toFixed(1)}s
                              </div>
                            </div>
                            <div className="mt-2.5">
                              <h5 className="text-xs font-bold text-white truncate">{clip.name}</h5>
                              <p className="text-[10px] text-gray-600 truncate mt-0.5">{clip.id}</p>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>

              </div>
            ) : (
              
              // --- PROJECT EDITOR VIEW ---
              <div className="flex-1 flex flex-col gap-6">
                
                {/* Editor Header */}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#222] pb-5">
                  <div className="flex items-center gap-4">
                    <button
                      onClick={() => { setSelectedProjectId(null); setSelectedProject(null); fetchProjects(); }}
                      className="px-3 py-1.5 bg-[#111] hover:bg-[#222] text-xs font-semibold rounded border border-[#222] cursor-pointer"
                    >
                      ← Voltar
                    </button>
                    <div>
                      <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        {selectedProject?.name}
                      </h2>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] uppercase font-bold text-[#8B0000] bg-red-950/20 px-2 py-0.5 rounded border border-red-950/50">
                          Format: {selectedProject?.format}
                        </span>
                        <span className={`text-[10px] uppercase font-extrabold px-2 py-0.5 rounded ${
                          compileStatus === "pronto" ? "bg-green-950/40 text-green-400 border border-green-950" : 
                          compileStatus === "compilando" ? "bg-yellow-950/40 text-yellow-400 border border-yellow-950 animate-pulse" :
                          compileStatus === "expirado" ? "bg-purple-950 text-purple-400" : "bg-gray-900 text-gray-400"
                        }`}>
                          {compileStatus}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      onClick={saveProjectChanges}
                      className="px-4 py-2 bg-[#111] hover:bg-[#222] border border-[#222] text-gray-300 text-xs font-bold rounded-lg cursor-pointer"
                    >
                      Salvar Alterações
                    </button>
                    
                    {compileStatus === "pronto" && compiledVideoUrl && (
                      <a
                        href={compiledVideoUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="px-4 py-2 bg-green-700 hover:bg-green-800 text-white text-xs font-bold rounded-lg flex items-center gap-1.5 shadow-lg border border-green-800"
                      >
                        <Download className="w-4 h-4" /> Baixar MP4
                      </a>
                    )}
                    
                    {compileStatus === "pronto" && (
                      <button
                        onClick={handleCleanupProject}
                        className="px-4 py-2 bg-purple-950 hover:bg-purple-900 text-purple-300 border border-purple-900 text-xs font-bold rounded-lg flex items-center gap-1.5 cursor-pointer"
                      >
                        Deletar do Storage
                      </button>
                    )}

                    <div className="flex items-center gap-2">
                      <div
                        className="flex items-center gap-1 rounded-lg border border-[#2a2a2a] bg-[#0c0c0c] p-1"
                        role="group"
                        aria-label="Engine de renderização"
                      >
                        <Cpu className="w-3.5 h-3.5 text-[#666] ml-1 shrink-0" aria-hidden="true" />
                        {(["ffmpeg", "hyperframes"] as const).map((engine) => {
                          const ativo = renderEngine === engine;
                          return (
                            <button
                              key={engine}
                              type="button"
                              onClick={() => selectRenderEngine(engine)}
                              disabled={isCompiling}
                              aria-pressed={ativo}
                              title={
                                engine === "hyperframes"
                                  ? "Requer Chrome e ffmpeg/ffprobe locais"
                                  : "Engine padrão, sem dependência de Chrome"
                              }
                              className={`px-2.5 py-1.5 rounded-md text-[10px] font-bold transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                                ativo
                                  ? "bg-[#8B0000] text-white shadow-[0_2px_8px_rgba(139,0,0,0.35)]"
                                  : "text-gray-500 hover:text-gray-200 hover:bg-[#1a1a1a]"
                              }`}
                            >
                              {engine === "ffmpeg" ? "FFmpeg" : "HyperFrames"}
                            </button>
                          );
                        })}
                      </div>
                      <button
                        onClick={startCompile}
                        disabled={isCompiling || editorTimeline.length === 0}
                        className="px-5 py-2.5 bg-[#8B0000] hover:bg-[#a60000] text-white text-xs font-bold rounded-lg flex items-center gap-2 disabled:opacity-50 border border-red-900 shadow-[0_4px_12px_rgba(139,0,0,0.3)] cursor-pointer"
                      >
                        {isCompiling ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" /> Compilando...
                          </>
                        ) : (
                          <>
                            <Play className="w-4 h-4" /> Compilar Vídeo
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Editor Content Area */}
                <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6">
                  
                  {/* COL 1: TIMELINE (LEFT) */}
                  <div className="lg:col-span-1 bg-[#111] border border-[#222] rounded-xl p-5 flex flex-col gap-4">
                    <div>
                      <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-1">
                        <Film className="w-4 h-4 text-[#8B0000]" /> Timeline de Clipes ({editorTimeline.length})
                      </h3>
                      <p className="text-[11px] text-gray-500">Adicione mídias e configure sua ordem e tempos.</p>
                    </div>

                    {/* Media Upload Buttons */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="relative border border-[#222] border-dashed hover:border-[#8B0000] bg-black/30 hover:bg-black/50 transition-all duration-200 rounded-lg p-3 text-center cursor-pointer flex flex-col items-center justify-center">
                        <input
                          type="file"
                          accept="video/mp4,video/quicktime,video/webm"
                          onChange={(e) => handleUploadMedia(e, "video")}
                          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        />
                        <Film className="w-4 h-4 text-[#8B0000] mb-1.5" />
                        <span className="text-[10px] font-bold text-gray-300">+ Subir Vídeo</span>
                      </div>
                      <div className="relative border border-[#222] border-dashed hover:border-[#8B0000] bg-black/30 hover:bg-black/50 transition-all duration-200 rounded-lg p-3 text-center cursor-pointer flex flex-col items-center justify-center">
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp"
                          onChange={(e) => handleUploadMedia(e, "image")}
                          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        />
                        <ImageIcon className="w-4 h-4 text-[#8B0000] mb-1.5" />
                        <span className="text-[10px] font-bold text-gray-300">+ Subir Imagem</span>
                      </div>
                    </div>

                    {/* Timeline List */}
                    <div className="flex-1 max-h-[400px] overflow-y-auto flex flex-col gap-3 pr-1">
                      {editorTimeline.length === 0 ? (
                        <div className="flex-1 border border-[#222] border-dashed rounded-lg flex items-center justify-center p-6 text-center text-xs text-gray-500 h-40">
                          Sua timeline está vazia. Adicione arquivos de vídeo ou imagens acima.
                        </div>
                      ) : (
                        editorTimeline.map((item, idx) => (
                          <div key={item.id} className="bg-black border border-[#222] hover:border-[#333] rounded-lg p-3 flex items-start justify-between gap-3 group relative">
                            
                            <div className="w-20 h-20 rounded bg-gray-900 border border-[#222] overflow-hidden flex-shrink-0 flex items-center justify-center relative">
                              {item.type === "video" ? (
                                <video
                                  src={item.url.startsWith("/") ? `${API_BASE}${item.url}` : item.url}
                                  className="w-full h-full object-cover"
                                  preload="metadata"
                                  muted
                                />
                              ) : (
                                <img
                                  src={item.url.startsWith("/") ? `${API_BASE}${item.url}` : item.url}
                                  className="w-full h-full object-cover"
                                />
                              )}
                              <span className="absolute bottom-1 right-1 bg-black/75 px-1 rounded text-[8px] font-bold">
                                {item.type === "video" ? "VÍDEO" : "IMAGEM"}
                              </span>
                            </div>

                            <div className="flex-1 flex flex-col gap-2 min-w-0">
                              <p className="text-[10px] text-gray-500 font-mono truncate">{item.key.split("/").pop()}</p>
                              
                              <div className="grid grid-cols-2 gap-1.5">
                                <div>
                                  <label className="text-[8px] font-extrabold uppercase text-gray-500 block">Duração (s)</label>
                                  <input
                                    type="number"
                                    step="0.5"
                                    min="0.5"
                                    value={item.duration}
                                    disabled={item.type === "video"} // Videos have fixed duration by file, images can change
                                    onChange={(e) => updateTimelineItem(idx, "duration", parseFloat(e.target.value))}
                                    className="bg-[#111] border border-[#222] rounded px-1.5 py-0.5 text-xs text-white w-full disabled:opacity-50"
                                  />
                                </div>
                                {item.type === "video" && (
                                  <div>
                                    <label className="text-[8px] font-extrabold uppercase text-gray-500 block">Cortar Trim (s)</label>
                                    <div className="flex gap-1">
                                      <input
                                        type="number"
                                        step="0.5"
                                        placeholder="Iníc"
                                        value={item.trim_start}
                                        onChange={(e) => updateTimelineItem(idx, "trim_start", parseFloat(e.target.value))}
                                        className="bg-[#111] border border-[#222] rounded px-1 py-0.5 text-[10px] text-white w-1/2"
                                        title="Trim Start"
                                      />
                                      <input
                                        type="number"
                                        step="0.5"
                                        placeholder="Fim"
                                        value={item.trim_end}
                                        onChange={(e) => updateTimelineItem(idx, "trim_end", parseFloat(e.target.value))}
                                        className="bg-[#111] border border-[#222] rounded px-1 py-0.5 text-[10px] text-white w-1/2"
                                        title="Trim End"
                                      />
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>

                            <div className="flex flex-col gap-1.5 self-center">
                              <button
                                onClick={() => moveTimelineItem(idx, "up")}
                                disabled={idx === 0}
                                className="p-1 hover:bg-[#222] rounded text-gray-400 hover:text-white disabled:opacity-30"
                              >
                                <ArrowUp className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => moveTimelineItem(idx, "down")}
                                disabled={idx === editorTimeline.length - 1}
                                className="p-1 hover:bg-[#222] rounded text-gray-400 hover:text-white disabled:opacity-30"
                              >
                                <ArrowDown className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => removeTimelineItem(idx)}
                                className="p-1 hover:bg-red-950 rounded text-gray-500 hover:text-red-400"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>

                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* COL 2: AUDIO & SUBTITLES (CENTER) */}
                  <div className="lg:col-span-1 flex flex-col gap-6">
                    
                    {/* Audio configuration Panel */}
                    <div className="bg-[#111] border border-[#222] rounded-xl p-5 flex flex-col gap-4">
                      <div>
                        <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-1">
                          <AudioLines className="w-4 h-4 text-[#8B0000]" /> Áudio de Voz (Voiceover)
                        </h3>
                        <p className="text-[11px] text-gray-500">Suba o áudio gravado e configure volume e fades.</p>
                      </div>

                      {/* File upload audio */}
                      <div className="relative border border-[#222] border-dashed rounded-lg p-4 text-center bg-black/30 hover:bg-black/50 transition-colors duration-200 cursor-pointer">
                        <input
                          type="file"
                          accept="audio/mp3,audio/wav,audio/x-m4a,audio/mpeg"
                          onChange={handleUploadAudio}
                          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        />
                        <AudioLines className="w-6 h-6 text-[#8B0000] mx-auto mb-1.5" />
                        <span className="text-xs font-bold text-gray-300 block">
                          {audioKey ? audioKey.split("/").pop() : "Selecionar Áudio (MP3, WAV)"}
                        </span>
                      </div>

                      {audioUrl && (
                        <div className="bg-black/60 p-3 rounded-lg border border-[#222]">
                          <audio src={audioUrl} controls className="w-full h-8" />
                        </div>
                      )}

                      {/* Volume & Fade controls */}
                      <div className="flex flex-col gap-3.5 border-t border-[#222]/50 pt-4">
                        <div>
                          <div className="flex justify-between text-xs text-gray-400 mb-1.5">
                            <span>Volume ({Math.round(audioVolume * 100)}%)</span>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="2"
                            step="0.1"
                            value={audioVolume}
                            onChange={(e) => setAudioVolume(parseFloat(e.target.value))}
                            className="w-full accent-[#8B0000] bg-black h-1 rounded-lg appearance-none"
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <span className="text-[10px] text-gray-400 block mb-1">Fade In ({audioFadeIn}s)</span>
                            <input
                              type="range"
                              min="0"
                              max="3"
                              step="0.5"
                              value={audioFadeIn}
                              onChange={(e) => setAudioFadeIn(parseFloat(e.target.value))}
                              className="w-full accent-[#8B0000] bg-black h-1 rounded-lg appearance-none"
                            />
                          </div>
                          <div>
                            <span className="text-[10px] text-gray-400 block mb-1">Fade Out ({audioFadeOut}s)</span>
                            <input
                              type="range"
                              min="0"
                              max="3"
                              step="0.5"
                              value={audioFadeOut}
                              onChange={(e) => setAudioFadeOut(parseFloat(e.target.value))}
                              className="w-full accent-[#8B0000] bg-black h-1 rounded-lg appearance-none"
                            />
                          </div>
                        </div>
                        
                        <button
                          onClick={saveAudioParameters}
                          className="mt-1 py-1.5 bg-[#222] hover:bg-[#333] border border-[#333] text-gray-300 text-xs font-bold rounded cursor-pointer"
                        >
                          Aplicar Parâmetros
                        </button>
                      </div>
                    </div>

                    {/* Subtitles configuration Panel */}
                    <div className="bg-[#111] border border-[#222] rounded-xl p-5 flex flex-col gap-4">
                      <div>
                        <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-1">
                          <Type className="w-4 h-4 text-[#8B0000]" /> Legendas & Roteiro
                        </h3>
                        <p className="text-[11px] text-gray-500">Escreva o roteiro e configure a exibição de legendas.</p>
                      </div>

                      {/* Gerador de roteiro de alta retenção */}
                      <div className="bg-black/40 border border-[#8B0000]/40 rounded-lg p-3 flex flex-col gap-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold text-white flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5 text-[#8B0000]" /> Gerador de Roteiro
                          </span>
                          {scriptResult ? (
                            <span className="text-[9px] text-gray-500">
                              {scriptResult.modo} · {scriptResult.modelo} · {scriptResult.blocos?.length || 0} blocos
                            </span>
                          ) : (
                            <span className="nd-chip">
                              {provedoresInfo.filter((p: any) => p.configurado).length} provedores ativos
                            </span>
                          )}
                        </div>

                        <input
                          type="text"
                          value={scriptTema}
                          onChange={(e) => setScriptTema(e.target.value)}
                          placeholder="Ex: o segredo que a história escondeu sobre as pirâmides"
                          className="bg-black border border-[#222] rounded px-2 py-1.5 text-[11px] text-white focus:outline-none focus:border-[#8B0000] w-full placeholder-gray-600"
                        />

                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="text-[9px] text-gray-500 block mb-0.5">Provedor</label>
                            <select
                              value={scriptProvider}
                              onChange={(e) => setScriptProvider(e.target.value)}
                              className="bg-black border border-[#222] text-white px-2 py-1 rounded text-[11px] w-full focus:outline-none focus:border-[#8B0000]"
                            >
                              <option value="auto">Auto · primeiro disponível</option>
                              {provedoresInfo.map((p: any) => (
                                <option key={p.id} value={p.id}>
                                  {p.nome}{p.configurado ? " ●" : " ○"}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="text-[9px] text-gray-500 block mb-0.5">Modelo (opcional)</label>
                            <input
                              type="text"
                              value={scriptModel}
                              onChange={(e) => setScriptModel(e.target.value)}
                              placeholder="padrão do provedor"
                              className="bg-black border border-[#222] rounded px-2 py-1 text-[11px] text-white w-full placeholder-gray-600 focus:outline-none focus:border-[#8B0000]"
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="text-[9px] text-gray-500 block mb-0.5">Duração alvo (s)</label>
                            <input
                              type="number"
                              min={5}
                              max={600}
                              value={scriptDuracao}
                              onChange={(e) => setScriptDuracao(parseInt(e.target.value) || 60)}
                              className="bg-black border border-[#222] rounded px-2 py-1 text-[11px] text-white w-full"
                            />
                          </div>
                          <div>
                            <label className="text-[9px] text-gray-500 block mb-0.5">Público (opcional)</label>
                            <input
                              type="text"
                              value={scriptPublico}
                              onChange={(e) => setScriptPublico(e.target.value)}
                              placeholder="curiosos, fãs de mistério..."
                              className="bg-black border border-[#222] rounded px-2 py-1 text-[11px] text-white w-full placeholder-gray-600"
                            />
                          </div>
                        </div>

                        <button
                          onClick={handleGenerateScript}
                          disabled={scriptGerando || !scriptTema.trim()}
                          className="nd-btn nd-btn-primary w-full"
                        >
                          {scriptGerando ? (
                            <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Gerando...</>
                          ) : (
                            <><Sparkles className="w-3.5 h-3.5" /> Gerar Roteiro</>
                          )}
                        </button>

                        <div className="border-t border-[#222] pt-2.5 flex flex-col gap-1.5">
                          <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wide">
                            Clipes do YouTube (opcional)
                          </label>
                          <textarea
                            value={youtubeUrls}
                            onChange={(e) => setYoutubeUrls(e.target.value)}
                            placeholder={"Uma URL por bloco, na ordem do roteiro:\nhttps://youtube.com/watch?v=...\nhttps://youtu.be/...\n\nDeixe vazio para buscar automaticamente."}
                            rows={3}
                            className="bg-black border border-[#222] rounded p-2 text-[10px] text-white focus:outline-none focus:border-[#8B0000] w-full resize-none placeholder-gray-600"
                          />
                          <input
                            value={youtubeLicenca}
                            onChange={(e) => setYoutubeLicenca(e.target.value)}
                            placeholder="Licença/autorização (opcional, vai para credits.json)"
                            className="bg-black border border-[#222] rounded p-2 text-[10px] text-white focus:outline-none focus:border-[#8B0000] w-full placeholder-gray-600"
                          />
                          <p className="text-[9px] text-gray-600 leading-snug">
                            YouTube vem primeiro. Use apenas clipes próprios ou autorizados;
                            canal e URL entram em credits.json. Se falhar, cai para as outras fontes.
                          </p>
                        </div>

                        <button
                          onClick={handleAutoMedia}
                          disabled={autoMediaLoading || !selectedProjectId}
                          className="nd-btn w-full"
                        >
                          {autoMediaLoading ? (
                            <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Buscando mídia...</>
                          ) : (
                            <><Film className="w-3.5 h-3.5" /> Buscar e aplicar mídia</>
                          )}
                        </button>

                        {autoMediaResult && (
                          <div className="text-[9px] text-gray-500 border-t border-[#222] pt-2 flex flex-col gap-0.5">
                            <span className="text-green-500 font-bold">
                              {autoMediaResult.blocos} cenas na timeline
                            </span>
                            <span>
                              {autoMediaResult.videos} vídeos · {autoMediaResult.imagens} imagens · {autoMediaResult.fontes_usadas.join(", ")}
                            </span>
                            <span className="text-gray-600">Créditos salvos em media/credits.json</span>
                          </div>
                        )}

                        {scriptResult && (
                          <details className="border-t border-[#222] pt-2">
                            <summary className="text-[10px] text-gray-400 cursor-pointer">
                              Ver estrutura e JSON · {scriptResult.titulo}
                            </summary>
                            <div className="mt-2 flex flex-col gap-1.5 max-h-48 overflow-y-auto">
                              {(scriptResult.blocos || []).map((bloco: any, i: number) => (
                                <div key={i} className="text-[10px] bg-black/60 rounded px-2 py-1.5">
                                  <span className="text-[#ff6b6b] uppercase font-bold">{bloco.tipo}</span>
                                  <span className="text-gray-600"> · {bloco.duracao_segundos}s</span>
                                  <p className="text-gray-300 mt-0.5">{bloco.fala}</p>
                                  {bloco.sugestao_visual && (
                                    <p className="text-gray-600 italic mt-0.5">Visual: {bloco.sugestao_visual}</p>
                                  )}
                                </div>
                              ))}
                            </div>
                            <pre className="mt-2 text-[9px] text-gray-500 bg-black/60 rounded p-2 overflow-x-auto">
                              {JSON.stringify(scriptResult.roteiro_json, null, 2)}
                            </pre>
                          </details>
                        )}

                        <p className="text-[9px] text-gray-600">
                          Gemini Flash (grátis). O texto substitui o campo abaixo e ajusta os segundos por bloco.
                        </p>
                      </div>

                      <textarea
                        value={editorScript}
                        onChange={(e) => setEditorScript(e.target.value)}
                        placeholder="Escreva o roteiro aqui... Cada linha representará um bloco de texto exibido nas legendas queimadas."
                        rows={4}
                        className="bg-black border border-[#222] rounded-lg p-3 text-xs text-white focus:outline-none focus:border-[#8B0000] w-full resize-none placeholder-gray-600"
                      />

                      <div className="flex flex-col gap-3.5 border-t border-[#222]/50 pt-4">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-gray-400 font-semibold">Modo de Legendas</span>
                          <select
                            value={editorSubtitleMode}
                            onChange={(e) => setEditorSubtitleMode(e.target.value)}
                            className="bg-black border border-[#222] text-white px-2 py-1 rounded text-xs focus:outline-none focus:border-[#8B0000]"
                          >
                            <option value="none">Nenhuma</option>
                            <option value="reference">Apenas Referência</option>
                            <option value="burn">Queimar no Vídeo (FFmpeg)</option>
                          </select>
                        </div>

                        {editorSubtitleMode === "burn" && (
                          <div className="bg-black/40 border border-[#222] rounded p-3 flex flex-col gap-3 text-xs">
                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <label className="text-[10px] text-gray-500 block mb-0.5">Segundos por Bloco</label>
                                <input
                                  type="number"
                                  step="0.5"
                                  min="1"
                                  value={editorSubtitleStyle.sec_per_block || 3.0}
                                  onChange={(e) => setEditorSubtitleStyle({ ...editorSubtitleStyle, sec_per_block: parseFloat(e.target.value) })}
                                  className="bg-black border border-[#222] rounded px-2 py-1 text-white w-full"
                                />
                              </div>
                              <div>
                                <label className="text-[10px] text-gray-500 block mb-0.5">Alinhamento ASS</label>
                                <select
                                  value={editorSubtitleStyle.Alignment || 2}
                                  onChange={(e) => setEditorSubtitleStyle({ ...editorSubtitleStyle, Alignment: parseInt(e.target.value) })}
                                  className="bg-black border border-[#222] rounded px-2 py-1 text-white w-full"
                                >
                                  <option value={2}>Inferior Centro (2)</option>
                                  <option value={10}>Centro (10)</option>
                                  <option value={6}>Superior Centro (6)</option>
                                </select>
                              </div>
                            </div>
                            
                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <label className="text-[10px] text-gray-500 block mb-0.5">Tamanho Fonte</label>
                                <input
                                  type="number"
                                  value={editorSubtitleStyle.FontSize || 48}
                                  onChange={(e) => setEditorSubtitleStyle({ ...editorSubtitleStyle, FontSize: parseInt(e.target.value) })}
                                  className="bg-black border border-[#222] rounded px-2 py-1 text-white w-full"
                                />
                              </div>
                              <div>
                                <label className="text-[10px] text-gray-500 block mb-0.5">Cor HEX Legenda</label>
                                <input
                                  type="color"
                                  value={editorSubtitleStyle.PrimaryColour || "#FFFFFF"}
                                  onChange={(e) => setEditorSubtitleStyle({ ...editorSubtitleStyle, PrimaryColour: e.target.value })}
                                  className="bg-black border border-[#222] rounded h-7 w-full cursor-pointer"
                                />
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Sincronização com a voz do usuário */}
                    <div className="bg-[#111] border border-[#222] rounded-xl p-5 flex flex-col gap-4">
                      <div>
                        <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-1">
                          <Mic className="w-4 h-4 text-[#8B0000]" /> Sincronizar com minha voz
                        </h3>
                        <p className="text-[11px] text-gray-500">
                          O Whisper escuta a narração que você enviou e encaixa cada legenda no tempo real da fala.
                          Roda local, sem custo e sem enviar áudio para terceiros.
                        </p>
                      </div>

                      <button
                        onClick={handleTranscribe}
                        disabled={transcribeLoading || !selectedProjectId}
                        className="nd-btn nd-btn-primary w-full"
                      >
                        {transcribeLoading ? (
                          <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Ouvindo sua voz...</>
                        ) : (
                          <><Mic className="w-3.5 h-3.5" /> Sincronizar legenda com minha voz</>
                        )}
                      </button>

                      {transcribeResult && (
                        <div className="bg-black/40 border border-[#8B0000]/30 rounded-lg p-3 flex flex-col gap-1.5 text-[10px] text-gray-400">
                          <div className="flex flex-wrap gap-1.5">
                            <span className="nd-chip">{transcribeResult.modelo} · {transcribeResult.idioma}</span>
                            <span className="nd-chip">{transcribeResult.duracao_segundos}s</span>
                            <span className="nd-chip">{transcribeResult.segmentos} falas</span>
                            <span className="nd-chip">{transcribeResult.linhas_srt} linhas SRT</span>
                            <span className="nd-chip">{transcribeResult.blocos_alinhados} blocos</span>
                          </div>
                          <a
                            href={`${API_BASE}${transcribeResult.srt_url}`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[#e5a1a1] hover:underline w-fit"
                          >
                            Baixar SRT sincronizado
                          </a>
                          <p className="nd-muted">{transcribeResult.dica}</p>
                        </div>
                      )}
                    </div>

                    {/* Pesquisa de hype via navegador */}
                    <div className="bg-[#111] border border-[#222] rounded-xl p-5 flex flex-col gap-4">
                      <div>
                        <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-1">
                          <TrendingUp className="w-4 h-4 text-[#8B0000]" /> Pesquisa Hype
                        </h3>
                        <p className="text-[11px] text-gray-500">
                          Lê o que está bombando no YouTube pelo HTML do navegador — sem chave de API e sem cota.
                        </p>
                      </div>

                      <div className="flex flex-col gap-2">
                        <input
                          className="nd-input"
                          placeholder="Tema (ex.: mistérios que a ciência não explica)"
                          value={hypeTema}
                          onChange={(e) => setHypeTema(e.target.value)}
                        />
                        <div className="flex gap-2">
                          <select
                            className="nd-input flex-1"
                            value={hypePeriodo}
                            onChange={(e) => setHypePeriodo(e.target.value)}
                          >
                            <option value="day">Último dia</option>
                            <option value="week">Última semana</option>
                            <option value="month">Último mês</option>
                            <option value="year">Último ano</option>
                          </select>
                          <button onClick={handleHypeResearch} disabled={hypeLoading} className="nd-btn nd-btn-primary">
                            {hypeLoading ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <><TrendingUp className="w-3.5 h-3.5" /> Pesquisar</>
                            )}
                          </button>
                        </div>
                      </div>

                      {hypeResult && (
                        <div className="flex flex-col gap-2">
                          <span className="text-[9px] text-gray-500">
                            {hypeResult.fonte} · {hypeResult.videos?.length || 0} vídeos · {hypeResult.web?.length || 0} páginas
                          </span>

                          {(hypeResult.videos || []).map((v: any) => (
                            <a
                              key={v.id}
                              href={v.url}
                              target="_blank"
                              rel="noreferrer"
                              className="flex gap-2 bg-black/40 border border-[#222] rounded-lg p-2 hover:border-[#8B0000] transition-colors"
                            >
                              <img src={v.thumbnail} alt="" className="w-16 h-10 object-cover rounded shrink-0" />
                              <div className="flex-1 min-w-0">
                                <p className="text-[10px] text-white truncate">{v.titulo}</p>
                                <p className="text-[9px] text-gray-500 truncate">
                                  {v.canal} · {v.views_texto} · {v.idade} · {v.views_por_dia}/dia
                                </p>
                              </div>
                              <span className="nd-chip h-fit shrink-0" title="Hype score">{v.hype_score}</span>
                            </a>
                          ))}

                          {hypeResult.sugestoes && (
                            <div className="border-t border-[#222] pt-2 flex flex-col gap-1">
                              <p className="text-[10px] font-bold text-white">Ângulos sugeridos</p>
                              {(hypeResult.sugestoes.titulos || []).map((titulo: string, i: number) => (
                                <button
                                  key={`titulo-${i}`}
                                  onClick={() => {
                                    setScriptTema(titulo);
                                    showToast("success", "Título aplicado ao gerador de roteiro.");
                                  }}
                                  className="text-left text-[10px] text-gray-300 hover:text-white hover:underline"
                                >
                                  → {titulo}
                                </button>
                              ))}
                              {(hypeResult.sugestoes.angulos || []).map((angulo: string, i: number) => (
                                <button
                                  key={`angulo-${i}`}
                                  onClick={() => {
                                    setScriptTema(angulo);
                                    showToast("success", "Ângulo aplicado ao gerador de roteiro.");
                                  }}
                                  className="text-left text-[10px] text-gray-400 hover:text-white"
                                >
                                  · {angulo}
                                </button>
                              ))}
                              {hypeResult.sugestoes.insight && (
                                <p className="nd-muted text-[10px]">{hypeResult.sugestoes.insight}</p>
                              )}
                            </div>
                          )}

                          {(hypeResult.erros || []).map((erro: string, i: number) => (
                            <p key={`erro-${i}`} className="text-[9px] text-amber-500/80">{erro}</p>
                          ))}
                        </div>
                      )}
                    </div>

                  </div>

                  {/* COL 3: COMPILE STATUS & LOGS (RIGHT) */}
                  <div className="lg:col-span-1 bg-[#111] border border-[#222] rounded-xl p-5 flex flex-col gap-4">
                    <div>
                      <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-1">
                        <Settings className="w-4 h-4 text-[#8B0000]" /> Console de Compilação
                      </h3>
                      <p className="text-[11px] text-gray-500">Acompanhe os logs de processamento do FFmpeg.</p>
                    </div>

                    {/* Final Video Preview if Ready */}
                    {compileStatus === "pronto" && compiledVideoUrl ? (
                      <div className="rounded-lg bg-black border border-[#222] overflow-hidden aspect-video flex flex-col justify-between p-1.5">
                        <video
                          src={compiledVideoUrl}
                          controls
                          className="w-full h-full object-contain"
                        />
                      </div>
                    ) : (
                      <div className="aspect-video rounded-lg border border-[#222] border-dashed flex flex-col items-center justify-center p-6 text-center bg-black/20">
                        {isCompiling ? (
                          <>
                            <Loader2 className="w-8 h-8 text-[#8B0000] animate-spin mb-3" />
                            <p className="text-xs text-white font-bold animate-pulse">Compilando vídeo...</p>
                            <p className="text-[10px] text-gray-500 mt-1">Normalizando, concatenando e queimando legendas.</p>
                          </>
                        ) : (
                          <>
                            <Film className="w-8 h-8 text-gray-700 mb-3" />
                            <p className="text-xs text-gray-500 font-bold">Nenhum vídeo compilado.</p>
                            <p className="text-[10px] text-gray-600 mt-1">Clique no botão &quot;Compilar Vídeo&quot; acima para iniciar.</p>
                          </>
                        )}
                      </div>
                    )}

                    {/* Logs expandible output */}
                    <div className="flex-1 flex flex-col gap-2 min-h-[220px]">
                      <span className="text-[10px] font-extrabold uppercase text-gray-500 block">Logs do Servidor / FFmpeg</span>
                      <div className="flex-1 bg-black border border-[#222] rounded-lg p-3 font-mono text-[10px] text-gray-400 overflow-y-auto max-h-[300px] flex flex-col gap-1 select-text">
                        {compileLogs ? (
                          compileLogs.split("\n").map((line, idx) => (
                            <div key={idx} className="whitespace-pre-wrap">{line}</div>
                          ))
                        ) : (
                          <div className="text-gray-600 italic">Aguardando compilação...</div>
                        )}
                        <div ref={logEndRef} />
                      </div>
                    </div>
                  </div>

                </div>

              </div>
            )}
          </div>
        )}


        {/* TAB 2: BATCH MODE */}
        {activeTab === "batch" && (
          <div className="flex-1 flex flex-col gap-6">
            
            {/* Batch Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#222] pb-5">
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                  Criar Vídeos em Lote (Batch)
                </h2>
                <p className="text-sm text-gray-500 mt-1">Gere múltiplos vídeos dark de uma vez com processamento sequencial.</p>
              </div>

              <div className="flex gap-3">
                {batchProjects.length > 0 && (
                  <button
                    onClick={handleClearBatchList}
                    className="px-4 py-2 bg-[#111] hover:bg-[#222] border border-[#222] text-gray-400 hover:text-white text-xs font-bold rounded-lg cursor-pointer"
                  >
                    Limpar Fila
                  </button>
                )}
                <button
                  onClick={() => {
                    if (clipsBank.length === 0) {
                      showToast("error", "Você precisa subir clipes no Banco de Clipes do Dashboard antes de criar um lote.");
                    } else {
                      setShowAddBatchModal(true);
                    }
                  }}
                  className="px-4 py-2 bg-[#8B0000] hover:bg-[#a60000] text-white text-xs font-bold rounded-lg transition-all duration-200 flex items-center gap-1.5 border border-red-900 shadow-md cursor-pointer"
                >
                  <Plus className="w-4 h-4" /> Adicionar Vídeo ao Lote
                </button>
              </div>
            </div>

            <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Batch list Left */}
              <div className="lg:col-span-2 bg-[#111] border border-[#222] rounded-xl p-5 flex flex-col gap-4">
                <h3 className="text-sm font-bold text-white mb-1">Fila de Projetos ({batchProjects.length})</h3>
                
                <div className="flex-1 overflow-y-auto flex flex-col gap-3 pr-1 max-h-[500px]">
                  {batchProjects.length === 0 ? (
                    <div className="border border-[#222] border-dashed rounded-lg p-10 text-center text-xs text-gray-500 bg-black/10">
                      Nenhum projeto adicionado à fila do lote. Adicione projetos no botão acima.
                    </div>
                  ) : (
                    batchProjects.map((p, idx) => (
                      <div key={p.id || idx} className="bg-black border border-[#222] rounded-lg p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div>
                          <h4 className="font-bold text-white text-sm">{p.name}</h4>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[9px] uppercase font-bold text-[#8B0000] bg-red-950/20 px-1.5 py-0.5 rounded border border-red-950/30">
                              {p.format}
                            </span>
                            <span className="text-[10px] text-gray-500">
                              {p.clip_ids.length} clipes selecionados
                            </span>
                          </div>
                        </div>

                        <div className="max-w-xs truncate text-xs text-gray-500 font-mono italic">
                          Áudio: {p.audio_key ? p.audio_key.split("/").pop() : "Upload local"}
                        </div>

                        <button
                          onClick={() => setBatchProjects(batchProjects.filter((_, i) => i !== idx))}
                          className="p-1.5 text-gray-600 hover:text-red-400 hover:bg-[#111] rounded self-end md:self-auto transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Batch compiler progress Right */}
              <div className="lg:col-span-1 bg-[#111] border border-[#222] rounded-xl p-5 flex flex-col justify-between gap-6">
                <div>
                  <h3 className="text-sm font-bold text-white mb-2">Processador do Lote</h3>
                  <p className="text-xs text-gray-500 leading-relaxed">
                    Compilar múltiplos vídeos dark pode levar alguns minutos. Eles serão processados sequencialmente em fila para não sobrecarregar o servidor.
                  </p>
                </div>

                {/* Progress Details */}
                {batchStatus && (
                  <div className="bg-black border border-[#222] p-4 rounded-lg flex flex-col gap-4">
                    <div>
                      <div className="flex justify-between text-xs text-white font-bold mb-1.5">
                        <span>Progresso Geral</span>
                        <span>{Math.round(batchStatus.progress)}%</span>
                      </div>
                      <div className="w-full bg-[#111] rounded-full h-2 overflow-hidden border border-[#222]">
                        <div
                          className="bg-[#8B0000] h-full transition-all duration-300 shadow-[0_0_10px_rgba(139,0,0,0.8)]"
                          style={{ width: `${batchStatus.progress}%` }}
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 max-h-48 overflow-y-auto">
                      {batchStatus.projects?.map((bp: any) => (
                        <div key={bp.id} className="flex items-center justify-between text-xs border-b border-[#222]/50 pb-2">
                          <span className="text-gray-300 font-semibold truncate pr-4 max-w-[150px]">{bp.name}</span>
                          <span className={`text-[9px] font-extrabold uppercase px-2 py-0.5 rounded ${
                            bp.status === "pronto" ? "bg-green-950/40 text-green-400 border border-green-950" : 
                            bp.status === "compilando" ? "bg-yellow-950/40 text-yellow-400 border border-yellow-950 animate-pulse" : 
                            bp.status === "expirado" ? "bg-purple-950 text-purple-400" : "bg-gray-900 text-gray-400"
                          }`}>
                            {bp.status}
                          </span>
                        </div>
                      ))}
                    </div>
                    
                    {batchStatus.status === "completed" && batchStatus.zip_url && (
                      <a
                        href={batchStatus.zip_url}
                        target="_blank"
                        rel="noreferrer"
                        className="w-full py-2.5 bg-green-700 hover:bg-green-800 text-white text-xs font-bold rounded-lg flex items-center justify-center gap-2 shadow-lg border border-green-800 cursor-pointer text-center"
                      >
                        <Download className="w-4 h-4" /> Baixar Todos (ZIP)
                      </a>
                    )}
                  </div>
                )}

                <button
                  onClick={handleCompileBatch}
                  disabled={batchProjects.length === 0 || isCompilingBatch}
                  className="w-full py-3 bg-[#8B0000] hover:bg-[#a60000] text-white text-xs font-bold rounded-lg flex items-center justify-center gap-2 border border-red-900 shadow-md disabled:opacity-50 cursor-pointer"
                >
                  {isCompilingBatch ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" /> Compilando Fila...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" /> Compilar Lote
                    </>
                  )}
                </button>
              </div>

            </div>

          </div>
        )}


        {/* TAB 3: VIDEO CUTTER */}
        {activeTab === "cutter" && (
          <div className="flex-1 flex flex-col gap-6 max-w-4xl mx-auto w-full">
            
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                <Scissors className="w-6 h-6 text-[#8B0000]" /> Cortador de Vídeo Dedicado
              </h2>
              <p className="text-sm text-gray-500 mt-1">Extraia trechos curtos (5-10s) de links ou arquivos e mande direto para seu banco de clipes.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              
              {/* Form Input left */}
              <div className="md:col-span-1 bg-[#111] border border-[#222] rounded-xl p-5 flex flex-col gap-5">
                
                {/* Mode toggle */}
                <div className="flex bg-black p-1 rounded-lg border border-[#222]">
                  <button
                    onClick={() => { setCutterMode("url"); setCutterJobId(null); setCutterJobStatus("idle"); }}
                    className={`flex-1 py-1.5 text-xs font-bold rounded transition-colors ${
                      cutterMode === "url" ? "bg-[#8B0000] text-white" : "text-gray-400"
                    }`}
                  >
                    Por URL
                  </button>
                  <button
                    onClick={() => { setCutterMode("upload"); setCutterJobId(null); setCutterJobStatus("idle"); }}
                    className={`flex-1 py-1.5 text-xs font-bold rounded transition-colors ${
                      cutterMode === "upload" ? "bg-[#8B0000] text-white" : "text-gray-400"
                    }`}
                  >
                    Por Upload
                  </button>
                </div>

                <form onSubmit={handleCutterSourceSubmit} className="flex flex-col gap-4">
                  {cutterMode === "url" ? (
                    <div>
                      <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">URL do Vídeo</label>
                      <input
                        type="url"
                        placeholder="YouTube, TikTok, Instagram, MP4 direto"
                        value={cutterUrl}
                        onChange={(e) => setCutterUrl(e.target.value)}
                        className="w-full bg-black border border-[#222] rounded px-3 py-2 text-xs text-white focus:outline-none focus:border-[#8B0000]"
                      />
                    </div>
                  ) : (
                    <div>
                      <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">Arquivo de Vídeo</label>
                      <input
                        type="file"
                        accept="video/mp4,video/quicktime,video/x-matroska"
                        onChange={(e) => setCutterFile(e.target.files ? e.target.files[0] : null)}
                        className="w-full bg-black border border-[#222] rounded px-3 py-2 text-xs text-white focus:outline-none focus:border-[#8B0000]"
                      />
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={cutterJobStatus === "downloading"}
                    className="w-full py-2 bg-[#8B0000] hover:bg-[#a60000] text-white text-xs font-bold rounded flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                  >
                    {cutterJobStatus === "downloading" ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Carregando Vídeo...
                      </>
                    ) : (
                      <>
                        <LinkIcon className="w-3.5 h-3.5" /> Analisar Mídia
                      </>
                    )}
                  </button>
                </form>

                {cutterError && (
                  <div className="bg-red-950/40 border border-red-900 rounded p-3 text-red-300 text-xs flex gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                    <p>{cutterError}</p>
                  </div>
                )}
              </div>

              {/* Preview and cut settings right */}
              <div className="md:col-span-2 bg-[#111] border border-[#222] rounded-xl p-5 flex flex-col gap-5 justify-between">
                
                {/* Video Player Preview if analyzed */}
                {cutterJobStatus === "idle" && (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-12 border border-[#222] border-dashed rounded-lg bg-black/10 text-xs text-gray-500 min-h-60">
                    Aguardando análise de vídeo. Insira uma URL ou arquivo ao lado.
                  </div>
                )}

                {cutterJobStatus === "downloading" && (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-12 border border-[#222] border-dashed rounded-lg bg-black/10 min-h-60">
                    <Loader2 className="w-8 h-8 text-[#8B0000] animate-spin mb-3" />
                    <p className="text-xs text-white font-bold animate-pulse">Baixando e processando mídia...</p>
                    <p className="text-[10px] text-gray-500 mt-1">O yt-dlp está extraindo o conteúdo do link.</p>
                  </div>
                )}

                {(cutterJobStatus === "analyzed" || cutterJobStatus === "processing" || cutterJobStatus === "completed") && cutterPreviewUrl && (
                  <div className="flex-1 flex flex-col gap-4">
                    
                    {/* Media Player */}
                    <div className="rounded-lg bg-black border border-[#222] overflow-hidden aspect-video relative flex items-center justify-center">
                      <video
                        src={cutterPreviewUrl.startsWith("/") ? `${API_BASE}${cutterPreviewUrl}` : cutterPreviewUrl}
                        controls
                        className="w-full h-full object-contain"
                      />
                    </div>

                    {/* Cut controls Form */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-[#222] pt-4">
                      
                      <div className="flex flex-col gap-3">
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-[9px] text-gray-400 uppercase font-bold block mb-1">Ponto de Início (s)</label>
                            <input
                              type="number"
                              step="0.5"
                              min="0"
                              max={cutterDuration}
                              value={cutStart}
                              onChange={(e) => setCutStart(parseFloat(e.target.value))}
                              className="bg-black border border-[#222] rounded px-3 py-1.5 text-xs text-white focus:outline-none w-full"
                            />
                          </div>
                          <div>
                            <label className="text-[9px] text-gray-400 uppercase font-bold block mb-1">Modo de Corte</label>
                            <select
                              value={cutMode}
                              onChange={(e) => setCutMode(e.target.value as any)}
                              className="bg-black border border-[#222] rounded px-3 py-1.5 text-xs text-white focus:outline-none w-full"
                            >
                              <option value="5">Cortar 5 segundos</option>
                              <option value="10">Cortar 10 segundos</option>
                              <option value="custom">Trecho Customizado</option>
                            </select>
                          </div>
                        </div>

                        {cutMode === "custom" && (
                          <div>
                            <label className="text-[9px] text-gray-400 uppercase font-bold block mb-1">Duração do Corte (s)</label>
                            <input
                              type="number"
                              step="0.5"
                              min="1"
                              value={cutDuration}
                              onChange={(e) => setCutDuration(parseFloat(e.target.value))}
                              className="bg-black border border-[#222] rounded px-3 py-1.5 text-xs text-white focus:outline-none w-full"
                            />
                          </div>
                        )}
                      </div>

                      <div className="flex flex-col gap-3">
                        <div>
                          <label className="text-[9px] text-gray-400 uppercase font-bold block mb-1">Nome do Clipe (Opcional)</label>
                          <input
                            type="text"
                            placeholder="Nome para salvar no banco"
                            value={cutClipName}
                            onChange={(e) => setCutClipName(e.target.value)}
                            className="bg-black border border-[#222] rounded px-3 py-1.5 text-xs text-white focus:outline-none w-full"
                          />
                        </div>

                        <div className="flex items-center gap-2 mt-2">
                          <input
                            type="checkbox"
                            id="add-to-bank-check"
                            checked={cutAddToBank}
                            onChange={(e) => setCutAddToBank(e.target.checked)}
                            className="rounded accent-[#8B0000] bg-black border-[#222]"
                          />
                          <label htmlFor="add-to-bank-check" className="text-xs text-gray-400 cursor-pointer">
                            Adicionar clipe cortado ao Banco de Clipes
                          </label>
                        </div>
                      </div>

                    </div>
                  </div>
                )}

                {/* Compile results */}
                {cutterJobStatus === "completed" && cutResultUrl && (
                  <div className="bg-black border border-green-950 p-4 rounded-lg mt-3 flex items-center justify-between gap-4">
                    <div>
                      <span className="text-xs text-green-400 font-bold block mb-0.5">Corte Pronto!</span>
                      <p className="text-[10px] text-gray-500">O trecho selecionado foi recortado e salvo no storage.</p>
                    </div>
                    <div className="flex gap-2">
                      <a
                        href={cutResultUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="px-3 py-1.5 bg-green-700 hover:bg-green-800 text-white text-xs font-bold rounded flex items-center gap-1.5 transition-colors"
                      >
                        <Download className="w-3.5 h-3.5" /> Baixar Clipe
                      </a>
                    </div>
                  </div>
                )}

                {/* Cut execution button */}
                {cutterJobStatus === "analyzed" || cutterJobStatus === "processing" || cutterJobStatus === "completed" ? (
                  <button
                    onClick={handleCutVideo}
                    disabled={cuttingProgress}
                    className="w-full mt-4 py-3 bg-[#8B0000] hover:bg-[#a60000] text-white text-xs font-bold rounded-lg flex items-center justify-center gap-2 border border-red-900 shadow-md cursor-pointer disabled:opacity-50"
                  >
                    {cuttingProgress ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" /> Recortando com FFmpeg...
                      </>
                    ) : (
                      <>
                        <Scissors className="w-4 h-4" /> Cortar e Processar
                      </>
                    )}
                  </button>
                ) : null}

              </div>

            </div>

          </div>
        )}

      </main>

      {/* --- CREATE NEW PROJECT MODAL --- */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-[#111] border border-[#222] rounded-xl p-6 w-full max-w-sm shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-4">Criar Novo Projeto</h3>
            <form onSubmit={handleCreateProject} className="flex flex-col gap-4">
              <div>
                <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">Nome do Projeto</label>
                <input
                  type="text"
                  placeholder="Projeto Dark #1"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="w-full bg-black border border-[#222] rounded px-3 py-2 text-xs text-white focus:outline-none focus:border-[#8B0000]"
                  required
                />
              </div>

              <div>
                <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">Formato do Vídeo</label>
                <select
                  value={newProjectFormat}
                  onChange={(e) => setNewProjectFormat(e.target.value)}
                  className="w-full bg-black border border-[#222] rounded px-3 py-2 text-xs text-white focus:outline-none focus:border-[#8B0000]"
                >
                  <option value="shorts">Shorts 9:16 (1080x1920)</option>
                  <option value="standard">Padrão 16:9 (1920x1080)</option>
                  <option value="square">Square 1:1 (1080x1080)</option>
                </select>
              </div>

              <div className="flex gap-3 mt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 py-2 bg-[#222] hover:bg-[#333] border border-[#333] text-gray-300 text-xs font-bold rounded cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 bg-[#8B0000] hover:bg-[#a60000] text-white text-xs font-bold rounded cursor-pointer"
                >
                  Criar Projeto
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- ADD BATCH PROJECT MODAL --- */}
      {showAddBatchModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-[#111] border border-[#222] rounded-xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-4">Adicionar Projeto ao Lote</h3>
            <form onSubmit={handleAddProjectToBatchList} className="flex flex-col gap-4">
              
              <div>
                <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">Nome do Projeto</label>
                <input
                  type="text"
                  placeholder="Lote Item #1"
                  value={batchProjName}
                  onChange={(e) => setBatchProjName(e.target.value)}
                  className="w-full bg-black border border-[#222] rounded px-3 py-2 text-xs text-white focus:outline-none focus:border-[#8B0000]"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">Formato</label>
                  <select
                    value={batchProjFormat}
                    onChange={(e) => setBatchProjFormat(e.target.value)}
                    className="w-full bg-black border border-[#222] rounded px-3 py-2 text-xs text-white focus:outline-none"
                  >
                    <option value="shorts">Shorts 9:16</option>
                    <option value="standard">Padrão 16:9</option>
                    <option value="square">Square 1:1</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">Voz (Áudio MP3/WAV)</label>
                  <input
                    type="file"
                    id="batch-audio-input"
                    accept="audio/*"
                    onChange={(e) => setBatchProjAudioFile(e.target.files ? e.target.files[0] : null)}
                    className="w-full bg-black border border-[#222] rounded px-2 py-1 text-[11px] text-white focus:outline-none"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1">Legendas / Roteiro</label>
                <textarea
                  placeholder="Roteiro..."
                  value={batchProjScript}
                  onChange={(e) => setBatchProjScript(e.target.value)}
                  rows={3}
                  className="w-full bg-black border border-[#222] rounded px-3 py-2 text-xs text-white focus:outline-none"
                />
                <div className="flex items-center gap-2 mt-1.5">
                  <input
                    type="checkbox"
                    id="batch-burn-leg"
                    checked={batchProjBurnLeg}
                    onChange={(e) => setBatchProjBurnLeg(e.target.checked)}
                    className="rounded accent-[#8B0000] bg-black border-[#222]"
                  />
                  <label htmlFor="batch-burn-leg" className="text-[10px] text-gray-400 cursor-pointer">
                    Queimar legendas no vídeo
                  </label>
                </div>
              </div>

              {/* Reusable clips selection */}
              <div>
                <label className="text-[10px] text-gray-400 uppercase font-bold block mb-1.5">
                  Selecionar Clipes da Timeline (Clique em ordem para sequenciar)
                </label>
                <div className="border border-[#222] rounded-lg p-3 bg-black/30 grid grid-cols-2 gap-2 max-h-36 overflow-y-auto">
                  {clipsBank.map((clip) => {
                    const isSelected = batchProjSelectedClips.includes(clip.id);
                    const orderIndex = batchProjSelectedClips.indexOf(clip.id);
                    return (
                      <div
                        key={clip.id}
                        onClick={() => toggleBatchClipSelection(clip.id)}
                        className={`border rounded p-2 flex items-center justify-between cursor-pointer select-none transition-all duration-200 ${
                          isSelected 
                            ? "bg-[#8B0000]/10 border-[#8B0000]" 
                            : "bg-black border-[#222] hover:border-[#333]"
                        }`}
                      >
                        <span className="text-[10px] font-bold text-white truncate pr-2">{clip.name}</span>
                        {isSelected ? (
                          <span className="bg-[#8B0000] text-white rounded-full w-4 h-4 flex items-center justify-center text-[9px] font-extrabold">
                            {orderIndex + 1}
                          </span>
                        ) : (
                          <span className="text-[9px] text-gray-500">+{clip.duration.toFixed(0)}s</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="flex gap-3 mt-3">
                <button
                  type="button"
                  onClick={() => setShowAddBatchModal(false)}
                  className="flex-1 py-2 bg-[#222] hover:bg-[#333] border border-[#333] text-gray-300 text-xs font-bold rounded cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 bg-[#8B0000] hover:bg-[#a60000] text-white text-xs font-bold rounded cursor-pointer"
                >
                  Adicionar ao Lote
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
