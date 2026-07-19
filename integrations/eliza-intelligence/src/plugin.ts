import type { Action, Provider } from "../node_modules/@elizaos/core/dist/types/components.js";
import type { Memory } from "../node_modules/@elizaos/core/dist/types/memory.js";
import type { Plugin } from "../node_modules/@elizaos/core/dist/types/plugin.js";
import type { State } from "../node_modules/@elizaos/core/dist/types/state.js";

import { opportunityObservationSchema } from "./contracts.js";
import type { OraclePublisher } from "./publisher.js";

export const oracleSafetyBoundaryProvider: Provider = {
  name: "ORACLE_SAFETY_BOUNDARY",
  description: "Explains the read-only boundary between Eliza scouts and Oracle execution.",
  private: false,
  get: async () => ({
    text: [
      "You may research and publish auditable market observations.",
      "You may not place, amend, or cancel broker orders.",
      "You may not modify prop-firm rules, portfolio ledger, or kill switches.",
      "Directional observations require timestamped evidence and invalidation conditions.",
    ].join(" "),
    data: { executionAccess: false, brokerCredentialsAvailable: false },
  }),
};

export function createPublishObservationAction(publisher: OraclePublisher): Action {
  return {
    name: "PUBLISH_ORACLE_OBSERVATION",
    similes: ["REPORT_MARKET_OPPORTUNITY", "PUBLISH_RISK_ALERT"],
    description: "Publish a read-only, evidence-backed opportunity observation to Oracle.",
    validate: async (_runtime, message: Memory) => {
      return opportunityObservationSchema.safeParse(message.content.oracleObservation).success;
    },
    handler: async (_runtime, message: Memory, _state?: State) => {
      const parsed = opportunityObservationSchema.parse(message.content.oracleObservation);
      await publisher.publish(parsed);
      return {
        success: true,
        text: `Observation ${parsed.observation_id} accepted by Oracle intelligence gateway`,
        data: {
          observationId: parsed.observation_id,
          executionAccess: false,
        },
      };
    },
  };
}

export function createOracleIntelligencePlugin(publisher: OraclePublisher): Plugin {
  return {
    name: "oracle-intelligence",
    description: "Read-only intelligence bridge from elizaOS to Oracle.",
    providers: [oracleSafetyBoundaryProvider],
    actions: [createPublishObservationAction(publisher)],
  };
}
