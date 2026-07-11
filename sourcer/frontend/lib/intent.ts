export type Intent = "interested" | "questions" | "declined" | "other";

export const intentColor: Record<string, string> = {
  interested: "text-green-400",
  questions: "text-amber-400",
  declined: "text-red-400",
  other: "text-[var(--muted)]",
};

export const intentLabel: Record<string, { label: string; variant: Intent }> = {
  interested: { label: "Interested", variant: "interested" },
  questions: { label: "Questions", variant: "questions" },
  declined: { label: "Declined", variant: "declined" },
  other: { label: "Unclear", variant: "other" },
};

export function intentVariant(intent?: string): Intent {
  if (intent === "interested") return "interested";
  if (intent === "questions") return "questions";
  if (intent === "declined") return "declined";
  return "other";
}
