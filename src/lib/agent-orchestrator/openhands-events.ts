import type { OpenHandsEvent } from "#/types/agent-server/core/openhands-event";

export type OrchestrationEventKind = "agent_message" | "tool_started" | "tool_completed" | "command_started" | "command_completed" | "file_changed" | "error" | "state_changed" | "paused" | "streaming" | "other";

export type OrchestrationEvent = { kind: OrchestrationEventKind; eventId: string | number; timestamp?: string; summary: string; sourceEvent: OpenHandsEvent };

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : {};
}

export function normalizeOpenHandsEvent(event: OpenHandsEvent): OrchestrationEvent {
  const raw = record(event);
  const type = String(raw.event || raw.kind || raw.type || "").toLowerCase();
  const id = (raw.id as string | number | undefined) ?? "unknown";
  const timestamp = typeof raw.timestamp === "string" ? raw.timestamp : undefined;
  const action = record(raw.action);
  const observation = record(raw.observation);
  if (type.includes("message")) return { kind: "agent_message", eventId: id, timestamp, summary: "Agent message received", sourceEvent: event };
  if (type.includes("error")) return { kind: "error", eventId: id, timestamp, summary: String(raw.message || raw.error || "OpenHands reported an error"), sourceEvent: event };
  if (type.includes("pause")) return { kind: "paused", eventId: id, timestamp, summary: "Execution paused", sourceEvent: event };
  if (type.includes("stream")) return { kind: "streaming", eventId: id, timestamp, summary: "Streaming update received", sourceEvent: event };
  if (type.includes("state")) return { kind: "state_changed", eventId: id, timestamp, summary: String(raw.value || "Conversation state changed"), sourceEvent: event };
  if (type.includes("action")) {
    const actionType = String(action.kind || action.type || action.command || "tool").toLowerCase();
    return { kind: actionType.includes("bash") || actionType.includes("command") || actionType.includes("cmdrun") || actionType.includes("terminal") ? "command_started" : actionType.includes("file") || actionType.includes("edit") ? "file_changed" : "tool_started", eventId: id, timestamp, summary: `OpenHands action: ${actionType}`, sourceEvent: event };
  }
  if (type.includes("observation")) {
    const observationType = String(observation.kind || observation.type || observation.command || "tool").toLowerCase();
    return { kind: observationType.includes("bash") || observationType.includes("command") || observationType.includes("cmdoutput") || observationType.includes("terminal") ? "command_completed" : observationType.includes("file") ? "file_changed" : "tool_completed", eventId: id, timestamp, summary: `OpenHands observation: ${observationType}`, sourceEvent: event };
  }
  return { kind: "other", eventId: id, timestamp, summary: "OpenHands event received", sourceEvent: event };
}
