import type { OpportunityObservation } from "./contracts.js";

export interface OraclePublisher {
  publish(observation: OpportunityObservation): Promise<void>;
}

export class HttpOraclePublisher implements OraclePublisher {
  public constructor(
    private readonly endpoint: string,
    private readonly apiKey?: string,
  ) {}

  public async publish(observation: OpportunityObservation): Promise<void> {
    const response = await fetch(this.endpoint, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(this.apiKey ? { "x-api-key": this.apiKey } : {}),
      },
      body: JSON.stringify(observation),
    });
    if (!response.ok) {
      throw new Error(`Oracle rejected observation with HTTP ${response.status}`);
    }
  }
}
