import type { Memory } from "../node_modules/@elizaos/core/dist/types/memory.js";
import { describe, expect, it } from "vitest";

import { createPublishObservationAction } from "./plugin.js";
import type { OraclePublisher } from "./publisher.js";

class RecordingPublisher implements OraclePublisher {
  public observations: unknown[] = [];

  public async publish(observation: unknown): Promise<void> {
    this.observations.push(observation);
  }
}

function message(observation: unknown): Memory {
  return { content: { oracleObservation: observation } } as Memory;
}

const observation = {
  observation_id: "obs-1",
  agent_id: "eliza-onchain-scout",
  event_time: "2026-07-18T12:00:00.000Z",
  available_at: "2026-07-18T12:00:01.000Z",
  instruments: ["BTC"],
  observation_type: "exchange_inflow",
  direction: "bearish",
  confidence: 0.8,
  novelty: 0.7,
  time_horizon: "4h",
  summary: "large exchange inflow",
  evidence: [
    {
      source: "official-feed",
      source_url: "https://example.invalid/feed",
      observed_at: "2026-07-18T12:00:00.000Z",
      available_at: "2026-07-18T12:00:01.000Z",
      content_hash: "hash",
      credibility: 0.9,
      excerpt: "",
    },
  ],
};

describe("Oracle intelligence plugin", () => {
  it("publishes validated observations without execution authority", async () => {
    const publisher = new RecordingPublisher();
    const action = createPublishObservationAction(publisher);

    expect(await action.validate({} as never, message(observation))).toBe(true);
    const result = await action.handler({} as never, message(observation));

    expect(publisher.observations).toHaveLength(1);
    expect(result?.data?.executionAccess).toBe(false);
  });

  it("rejects directional observations without evidence", async () => {
    const action = createPublishObservationAction(new RecordingPublisher());
    expect(
      await action.validate({} as never, message({ ...observation, evidence: [] })),
    ).toBe(false);
  });
});
