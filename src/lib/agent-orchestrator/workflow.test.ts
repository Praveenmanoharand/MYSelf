import { describe, expect, it } from "vitest";
import { runnableSteps, transitionStep, type Workflow } from "./workflow";

const workflow: Workflow = { id: "w1", name: "Proposal", createdAt: "now", updatedAt: "now", steps: [{ id: "research", title: "Research", dependsOn: [], status: "queued", attempts: 0 }, { id: "proposal", title: "Proposal", dependsOn: ["research"], status: "queued", attempts: 0 }] };

describe("workflow dependencies", () => {
  it("only returns steps whose dependencies are complete", () => {
    expect(runnableSteps(workflow).map((step) => step.id)).toEqual(["research"]);
  });

  it("rejects running a blocked step", () => {
    expect(() => transitionStep(workflow, "proposal", "running")).toThrow("dependencies");
  });
});
