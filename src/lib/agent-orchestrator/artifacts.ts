export type ArtifactType = "source" | "document" | "pdf" | "report" | "image" | "archive" | "log" | "research";
export type AgentArtifact = { id: string; taskId: string; name: string; type: ArtifactType; location: string; createdAt: string; verified: boolean };

export function createArtifact(input: Omit<AgentArtifact, "id" | "createdAt" | "verified">): AgentArtifact {
  if (!input.location.trim()) throw new Error("Artifact location is required.");
  return { ...input, id: crypto.randomUUID(), createdAt: new Date().toISOString(), verified: false };
}

export function verifyArtifact(artifact: AgentArtifact, exists: boolean): AgentArtifact {
  if (!exists) throw new Error(`Artifact was not found at ${artifact.location}.`);
  return { ...artifact, verified: true };
}
