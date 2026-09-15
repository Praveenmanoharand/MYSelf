export type WorkflowStepStatus = "queued" | "planning" | "running" | "waiting_for_user" | "waiting_for_tool" | "completed" | "failed" | "retrying" | "cancelled";
export type WorkflowStep = { id: string; title: string; dependsOn: string[]; status: WorkflowStepStatus; attempts: number; error?: string };
export type Workflow = { id: string; name: string; steps: WorkflowStep[]; createdAt: string; updatedAt: string };

export function runnableSteps(workflow: Workflow): WorkflowStep[] {
  const byId = new Map(workflow.steps.map((step) => [step.id, step]));
  return workflow.steps.filter((step) => step.status === "queued" && step.dependsOn.every((dependency) => byId.get(dependency)?.status === "completed"));
}

export function transitionStep(workflow: Workflow, stepId: string, status: WorkflowStepStatus, error?: string): Workflow {
  const step = workflow.steps.find((item) => item.id === stepId);
  if (!step) throw new Error(`Unknown workflow step: ${stepId}`);
  if (status === "running" && !runnableSteps(workflow).some((item) => item.id === stepId)) throw new Error("Step dependencies are not complete.");
  return { ...workflow, steps: workflow.steps.map((item) => item.id === stepId ? { ...item, status, attempts: status === "retrying" ? item.attempts + 1 : item.attempts, error } : item), updatedAt: new Date().toISOString() };
}
