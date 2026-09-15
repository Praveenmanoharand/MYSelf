export type SkillDefinition = {
  name: string;
  description: string;
  instructions: string;
};

const skillFiles = import.meta.glob("../../../skills/*/SKILL.md", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

function parseSkill(source: string): SkillDefinition | null {
  const frontMatter = source.match(/^---\s*\n([\s\S]*?)\n---/);
  if (!frontMatter) return null;
  const fields = Object.fromEntries(
    frontMatter[1]
      .split("\n")
      .map((line) => line.match(/^([\w-]+):\s*(.*)$/))
      .filter((match): match is RegExpMatchArray => Boolean(match))
      .map((match) => [match[1], match[2].trim()]),
  );
  if (!fields.name || !fields.description) return null;
  return { name: fields.name, description: fields.description, instructions: source.replace(frontMatter[0], "").trim() };
}

export function discoverSkills(): SkillDefinition[] {
  return Object.values(skillFiles).map(parseSkill).filter((skill): skill is SkillDefinition => Boolean(skill)).sort((a, b) => a.name.localeCompare(b.name));
}

const rules: Array<[RegExp, string[]]> = [
  [/\b(build|code|debug|api|database|frontend|backend|project|implement|test)\b/i, ["project-builder", "coding"]],
  [/\b(research|sources|compare|citations?|current information|investigate)\b/i, ["research", "data-analysis"]],
  [/\b(proposal|client|freelanc|quotation|scope|deliverables?)\b/i, ["freelancer", "proposal-generator", "document-generator"]],
  [/\b(document|report|resume|cv|meeting notes|technical documentation)\b/i, ["document-generator", "content-writer"]],
  [/\b(workflow|automate|sequence|pipeline|approval|schedule)\b/i, ["workflow-agent"]],
  [/\b(data|csv|spreadsheet|metrics|analy[sz]e)\b/i, ["data-analysis"]],
];

export function selectSkills(request: string, skills = discoverSkills()): SkillDefinition[] {
  const selected = new Set<string>(["core-agent"]);
  for (const [pattern, names] of rules) if (pattern.test(request)) names.forEach((name) => selected.add(name));
  return skills.filter((skill) => selected.has(skill.name));
}

export function buildSkillContext(request: string): string {
  return selectSkills(request).map((skill) => `## ${skill.name}\n${skill.instructions}`).join("\n\n");
}
