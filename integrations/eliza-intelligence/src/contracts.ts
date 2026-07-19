import { z } from "zod";

export const evidenceReferenceSchema = z.object({
  source: z.string().min(1),
  source_url: z.string().url().or(z.literal("")).default(""),
  observed_at: z.string().datetime(),
  available_at: z.string().datetime(),
  content_hash: z.string().min(1),
  credibility: z.number().min(0).max(1),
  excerpt: z.string().default(""),
});

export const opportunityObservationSchema = z.object({
  observation_id: z.string().min(1),
  agent_id: z.string().min(1),
  event_time: z.string().datetime(),
  available_at: z.string().datetime(),
  instruments: z.array(z.string().min(1)).min(1),
  observation_type: z.string().min(1),
  direction: z.enum(["bullish", "bearish", "neutral", "hedge"]),
  confidence: z.number().min(0).max(1),
  novelty: z.number().min(0).max(1),
  time_horizon: z.string().min(1),
  summary: z.string().min(1),
  evidence: z.array(evidenceReferenceSchema).default([]),
  invalidation_conditions: z.array(z.string()).default([]),
  prompt_version: z.string().default(""),
  model: z.string().default(""),
}).superRefine((observation, context) => {
  if (new Date(observation.available_at) < new Date(observation.event_time)) {
    context.addIssue({ code: "custom", message: "available_at cannot precede event_time" });
  }
  if (observation.direction !== "neutral" && observation.evidence.length === 0) {
    context.addIssue({ code: "custom", message: "directional observations require evidence" });
  }
});

export type OpportunityObservation = z.infer<typeof opportunityObservationSchema>;
