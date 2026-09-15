import { describe, expect, it } from "vitest";
import { normalizeOpenHandsEvent } from "./openhands-events";

describe("normalizeOpenHandsEvent", () => {
  it("maps actual action and observation-shaped events to categories", () => {
    const action = normalizeOpenHandsEvent({ id: 1, event: "ActionEvent", action: { type: "CmdRunAction", command: "npm test" } } as never);
    const observation = normalizeOpenHandsEvent({ id: 2, event: "ObservationEvent", observation: { type: "CmdOutputObservation", content: "ok" } } as never);
    expect(action.kind).toBe("command_started");
    expect(observation.kind).toBe("command_completed");
  });

  it("preserves errors instead of converting them into success", () => {
    const event = normalizeOpenHandsEvent({ id: "e1", event: "AgentErrorEvent", message: "command failed" } as never);
    expect(event.kind).toBe("error");
    expect(event.summary).toContain("command failed");
  });
});
