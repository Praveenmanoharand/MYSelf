import { getAgentServerHttpClientOptions } from "../agent-server-client-options";
import ConversationService from "../conversation-service/conversation-service.api";

export type OrchestrationStatus =
  | "queued"
  | "planning"
  | "running"
  | "waiting_for_user"
  | "waiting_for_tool"
  | "retrying"
  | "completed"
  | "failed"
  | "cancelled";

export interface OrchestrationTask {
  id: string;
  session_id: string;
  request: string;
  mode: string;
  workspace: string;
  classification: string;
  selected_skills: string[];
  execution_plan: string[];
  status: OrchestrationStatus;
  errors: string[];
  artifacts: Array<Record<string, unknown>>;
  conversation_id: string | null;
  model: string | null;
  provider: string | null;
  fallback_model: string | null;
}

export interface OrchestrationEvent {
  id: string;
  task_id: string;
  kind: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

class OrchestrationService {
  private static async request<T>(
    path: string,
    init?: RequestInit,
  ): Promise<T> {
    const options = getAgentServerHttpClientOptions({
      sessionApiKey: ConversationService.getCurrentConversation()?.session_api_key,
    });
    const response = await fetch(`${options.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(options.apiKey ? { "X-Session-API-Key": options.apiKey } : {}),
        ...init?.headers,
      },
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Orchestration request failed (${response.status}): ${detail}`);
    }
    return (await response.json()) as T;
  }

  static createTask(input: {
    request: string;
    mode?: string;
    workspace?: string;
    repository?: string;
    model?: string;
    fallback_model?: string;
  }): Promise<{ task: OrchestrationTask }> {
    return this.request("/api/v1/orchestration/tasks", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  static getTask(taskId: string): Promise<{ task: OrchestrationTask }> {
    return this.request(`/api/v1/orchestration/tasks/${encodeURIComponent(taskId)}`);
  }

  static cancelTask(taskId: string): Promise<{ task: OrchestrationTask }> {
    return this.request(`/api/v1/orchestration/tasks/${encodeURIComponent(taskId)}/cancel`, {
      method: "POST",
    });
  }

  static resumeTask(
    taskId: string,
    message?: string,
  ): Promise<{ task: OrchestrationTask }> {
    return this.request(`/api/v1/orchestration/tasks/${encodeURIComponent(taskId)}/resume`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
  }

  static getEvents(taskId: string, pageId?: string): Promise<{
    items: OrchestrationEvent[];
    next_page_id: string | null;
  }> {
    const query = pageId ? `?page_id=${encodeURIComponent(pageId)}` : "";
    return this.request(
      `/api/v1/orchestration/tasks/${encodeURIComponent(taskId)}/events${query}`,
    );
  }
}

export default OrchestrationService;
