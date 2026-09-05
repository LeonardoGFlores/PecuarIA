import { describe, expect, it } from "vitest";
import { generateAnalysis } from "../analysis/agent.js";
import { aggregateProfile } from "../analysis/aggregator.js";

describe("generateAnalysis", () => {
  it("returns a not-configured explanation when ANTHROPIC_API_KEY is missing", async () => {
    delete process.env.ANTHROPIC_API_KEY;
    const profile = aggregateProfile({ name: "Fazenda Boa Vista" }, []);
    const analysis = await generateAnalysis(profile);
    expect(analysis.model).toBe("none");
    expect(analysis.profileAnalysis).toMatch(/ANTHROPIC_API_KEY/);
  });
});
