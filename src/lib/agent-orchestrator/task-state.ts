import { selectSkills, type SkillDefinition } from "./skills";

export type TaskStatus = "queued" | "planning" | "running" | "waiting_for_user" | "waiting_for_tool" | "completed" | "failed" | "retrying" | "cancelled";
export type TaskType = "coding" | "research" | "proposal" | "document" | "workflow" | "data-analysis" | "general";

export type AgentTask = {
  id: string;
  request: string;
  type: TaskType;
  selectedSkills: string[];
  plan: string[];
  currentStep: number;
  completedSteps: number[];
  pendingSteps: number[];
  errors: string[];
  artifacts: string[];
  status: TaskStatus;
  createdAt: string;
  updatedAt: string;
};

const STORAGE_KEY = "oh:agent-tasks";

export function classifyTask(request: string): TaskType {
  if (/\b(build|code|debug|api|database|implement|project)\b/i.test(request)) return "coding";
  if (/\b(research|sources|citations?|compare|investigate)\b/i.test(request)) return "research";
  if (/\b(proposal|client|freelanc|quotation)\b/i.test(request)) return "proposal";
  if (/\b(document|report|resume|cv|notes)\b/i.test(request)) return "document";
  if (/\b(workflow|automate|pipeline|approval)\b/i.test(request)) return "workflow";
  if (/\b(data|csv|spreadsheet|metrics|analy[sz]e)\b/i.test(request)) return "data-analysis";
  return "general";
}

export function createAgentTask(request: string): AgentTask {
  const now = new Date().toISOString();
  const plan = ["Understand request", "Select skills and tools", "Execute through connected OpenHands backend", "Validate result", "Prepare deliverables"];
  return { id: crypto.randomUUID(), request, type: classifyTask(request), selectedSkills: selectSkills(request).map((skill) => skill.name), plan, currentStep: 0, completedSteps: [], pendingSteps: plan.map((_, index) => index), errors: [], artifacts: [], status: "queued", createdAt: now, updatedAt: now };
}

export function loadAgentTasks(): AgentTask[] {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as AgentTask[]; } catch { return []; }
}

export function saveAgentTask(task: AgentTask): AgentTask {
  const tasks = loadAgentTasks().filter((item) => item.id !== task.id);
  const updated = { ...task, updatedAt: new Date().toISOString() };
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify([updated, ...tasks].slice(0, 50))); } catch { /* persistence is best effort */ }
  return updated;
}

export function updateAgentTask(task: AgentTask, patch: Partial<AgentTask>): AgentTask { return saveAgentTask({ ...task, ...patch }); }

export type { SkillDefinition };
