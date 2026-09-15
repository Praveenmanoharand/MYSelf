export type ModelRoute = { provider: string; model: string; isFallback: boolean; timeoutMs: number; maxRetries: number };

function env(name: string): string | undefined {
  return (import.meta.env as Record<string, string | undefined>)[name];
}

export function getModelRoutes(taskType?: string): ModelRoute[] {
  const primary = env("VITE_PRIMARY_MODEL") || env("VITE_OPENROUTER_MODEL");
  const fallback = env("VITE_FALLBACK_MODEL");
  const provider = env("VITE_MODEL_PROVIDER") || (env("VITE_OPENROUTER_API_KEY") ? "openrouter" : "agent-backend");
  const taskModel = taskType ? env(`VITE_${taskType.toUpperCase().replace(/-/g, "_")}_MODEL`) : undefined;
  const routes: ModelRoute[] = [];
  if (taskModel || primary) routes.push({ provider, model: taskModel || primary || "backend-configured", isFallback: false, timeoutMs: Number(env("VITE_MODEL_TIMEOUT_MS") || 60000), maxRetries: Number(env("VITE_MODEL_MAX_RETRIES") || 2) });
  if (fallback) routes.push({ provider, model: fallback, isFallback: true, timeoutMs: Number(env("VITE_MODEL_TIMEOUT_MS") || 60000), maxRetries: Number(env("VITE_MODEL_MAX_RETRIES") || 2) });
  return routes;
}
