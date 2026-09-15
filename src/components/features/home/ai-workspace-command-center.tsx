import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  Code2,
  FileText,
  GitBranch,
  Layers3,
  Search,
  Sparkles,
  Workflow,
} from "lucide-react";
import { useNavigate } from "react-router";
import { useActiveBackend } from "#/contexts/active-backend-context";
import { useLlmConfigured } from "#/hooks/use-llm-configured";
import OrchestrationService, {
  type OrchestrationEvent,
  type OrchestrationTask,
} from "#/api/orchestration-service/orchestration-service.api";
import { selectSkills } from "#/lib/agent-orchestrator/skills";

type WorkspaceMode = {
  title: string;
  description: string;
  prompt: string;
  icon: typeof Code2;
  accent: string;
};

const MODES: WorkspaceMode[] = [
  {
    title: "Build software",
    description: "Plan, code, test, and fix a project with an agent in your workspace.",
    prompt: "Create a small Python project with a README and one Python file.",
    icon: Code2,
    accent: "text-cyan-300",
  },
  {
    title: "Research & compare",
    description: "Collect sources, compare evidence, and produce a structured result.",
    prompt: "Research this topic, collect reliable sources, compare the findings, and return a structured report with citations: ",
    icon: Search,
    accent: "text-violet-300",
  },
  {
    title: "Freelancer proposal",
    description: "Turn client requirements into scope, quotation, proposal, and delivery copy.",
    prompt: "Create a client-ready freelancer proposal. Extract requirements, define scope and assumptions, prepare a quotation, and draft the proposal: ",
    icon: FileText,
    accent: "text-amber-300",
  },
  {
    title: "Create a document",
    description: "Draft reports, technical docs, meeting notes, CV content, and project documentation.",
    prompt: "Create a professional structured document about: ",
    icon: BookOpen,
    accent: "text-emerald-300",
  },
];

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export function AiWorkspaceCommandCenter() {
  const [activeMode, setActiveMode] = useState("Build software");
  const [request, setRequest] = useState(MODES[0].prompt);
  const [activeTask, setActiveTask] = useState<OrchestrationTask | null>(null);
  const [events, setEvents] = useState<OrchestrationEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();
  const { backend } = useActiveBackend();
  const { isConfigured, isLoading } = useLlmConfigured();
  const selectedMode = MODES.find((mode) => mode.title === activeMode) ?? MODES[0];

  useEffect(() => {
    setRequest(selectedMode.prompt);
  }, [selectedMode]);

  useEffect(() => {
    if (!activeTask || TERMINAL_STATUSES.has(activeTask.status)) return undefined;
    let cancelled = false;
    const poll = async () => {
      try {
        const [taskResponse, eventResponse] = await Promise.all([
          OrchestrationService.getTask(activeTask.id),
          OrchestrationService.getEvents(activeTask.id),
        ]);
        if (!cancelled) {
          setActiveTask(taskResponse.task);
          setEvents(eventResponse.items);
        }
      } catch (pollError) {
        if (!cancelled) setError(pollError instanceof Error ? pollError.message : String(pollError));
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeTask]);

  const submitTask = async () => {
    const trimmed = request.trim();
    if (!trimmed) return;
    setIsSubmitting(true);
    setError(null);
    setEvents([]);
    try {
      const response = await OrchestrationService.createTask({
        request: trimmed,
        mode: activeMode === "Build software" ? "coding" : activeMode,
      });
      setActiveTask(response.task);
      const eventResponse = await OrchestrationService.getEvents(response.task.id);
      setEvents(eventResponse.items);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : String(submitError));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="mx-auto w-full max-w-[1100px] px-4 pt-8 md:px-8 lg:px-10">
      <div className="relative overflow-hidden rounded-[28px] border border-white/10 bg-[#111722] px-6 py-7 shadow-2xl shadow-black/20 md:px-9 md:py-9">
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="relative flex flex-col gap-8">
          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-start">
            <div>
              <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.22em] text-cyan-300/80"><Sparkles className="h-4 w-4" />Your AI workbench</div>
              <h1 className="max-w-2xl text-3xl font-semibold tracking-tight text-white md:text-4xl">One agent for the work that moves projects forward.</h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400 md:text-base">Submit a goal in plain language. The real OpenHands agent will execute it in the connected workspace and stream its task state and events here.</p>
            </div>
            <div className="flex shrink-0 items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-300"><span className={`h-2 w-2 rounded-full ${isLoading ? "bg-amber-300" : isConfigured ? "bg-emerald-400" : "bg-rose-400"}`} />{isLoading ? "Checking agent" : isConfigured ? "Agent ready" : "Backend/model setup needed"}</div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <StatusTile icon={GitBranch} label="Active backend" value={backend.name || backend.kind} />
            <StatusTile icon={Layers3} label="Execution context" value={backend.kind === "local" ? "Local workspace" : "Connected project"} />
            <StatusTile icon={CheckCircle2} label="Execution" value={activeTask ? activeTask.status : "Ready for a real task"} />
          </div>

          <div>
            <div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold text-white">Choose a starting point</h2><span className="text-xs text-slate-500">Tasks run through Agent Server</span></div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {MODES.map((mode) => {
                const Icon = mode.icon;
                const isActive = mode.title === activeMode;
                return <button key={mode.title} type="button" onClick={() => setActiveMode(mode.title)} className={`group rounded-2xl border p-4 text-left transition ${isActive ? "border-cyan-300/50 bg-cyan-300/[0.08]" : "border-white/10 bg-white/[0.025] hover:border-white/20 hover:bg-white/[0.05]"}`}><Icon className={`mb-5 h-5 w-5 ${mode.accent}`} /><div className="text-sm font-semibold text-white">{mode.title}</div><div className="mt-2 text-xs leading-5 text-slate-400">{mode.description}</div></button>;
              })}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-black/10 p-4 md:p-5">
            <div className="mb-3 flex items-center justify-between"><div><div className="text-sm font-medium text-white">{selectedMode.title}</div><div className="mt-1 text-[11px] text-slate-500">Skills: {selectSkills(selectedMode.prompt).map((skill) => skill.name).join(" · ")}</div></div><button type="button" onClick={() => navigate("/automations")} className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs font-medium text-slate-300 transition hover:bg-white/[0.06]">Workflows <ArrowUpRight className="h-3.5 w-3.5" /></button></div>
            <textarea value={request} onChange={(event) => setRequest(event.target.value)} rows={3} className="w-full resize-y rounded-xl border border-white/10 bg-slate-950/60 px-3 py-3 text-sm text-slate-200 outline-none ring-cyan-300/40 placeholder:text-slate-600 focus:ring-2" placeholder="Describe the real task for OpenHands" />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3"><div className="text-xs text-slate-500">No simulated responses. Errors from the real backend are shown here.</div><button type="button" onClick={() => void submitTask()} disabled={isSubmitting || isLoading || !request.trim()} className="inline-flex items-center gap-2 rounded-lg bg-cyan-300 px-4 py-2 text-xs font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-40">{isSubmitting ? "Creating task…" : "Run real task"} <ArrowUpRight className="h-3.5 w-3.5" /></button></div>
          </div>

          {error ? <div className="rounded-xl border border-rose-400/30 bg-rose-400/10 p-3 text-xs text-rose-200">{error}</div> : null}
          {activeTask ? <div className="grid gap-4 md:grid-cols-[0.8fr_1.2fr]">
            <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-4"><div className="text-xs uppercase tracking-[0.16em] text-slate-500">Real task</div><div className="mt-2 break-all font-mono text-[11px] text-cyan-200">{activeTask.id}</div><div className="mt-3 text-sm font-semibold text-white">{activeTask.status}</div><div className="mt-2 text-xs text-slate-400">{activeTask.classification} · {activeTask.provider ?? "configured provider"}</div><div className="mt-4 text-xs text-slate-500">Artifacts verified in workspace: {activeTask.artifacts.length}</div>{activeTask.artifacts.length ? <ul className="mt-2 space-y-1 text-xs text-emerald-200">{activeTask.artifacts.slice(0, 8).map((artifact) => <li key={String(artifact.path)}>✓ {String(artifact.path)}</li>)}</ul> : null}</div>
            <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4"><div className="mb-2 text-xs uppercase tracking-[0.16em] text-slate-500">Live OpenHands events</div><div className="max-h-52 space-y-2 overflow-auto pr-1">{events.length ? events.map((event) => <div key={event.id} className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2"><div className="font-mono text-[10px] text-cyan-200">{event.kind}</div><div className="mt-1 truncate text-[10px] text-slate-500">{event.timestamp}</div></div>) : <div className="text-xs text-slate-600">Waiting for events from Agent Server…</div>}</div></div>
          </div> : null}
        </div>
      </div>
    </section>
  );
}

function StatusTile({ icon: Icon, label, value }: { icon: typeof GitBranch; label: string; value: string }) {
  return <div className="rounded-xl border border-white/10 bg-white/[0.025] px-4 py-3"><div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-slate-500"><Icon className="h-3.5 w-3.5" />{label}</div><div className="mt-2 truncate text-sm font-medium text-slate-200">{value}</div></div>;
}

export default AiWorkspaceCommandCenter;
