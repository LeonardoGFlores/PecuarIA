import { describe, expect, it } from "vitest";
import { aggregateProfile, renderProfileForAgent } from "../analysis/aggregator.js";
import type { SourceResult } from "../types.js";

describe("aggregateProfile", () => {
  it("bundles criteria and source results into one profile", () => {
    const sources: SourceResult[] = [
      { source: "cnpj", status: "ok", data: { cnpj: "123" }, fetchedAt: "now" },
    ];
    const profile = aggregateProfile({ name: "Fazenda Boa Vista" }, sources);
    expect(profile.criteria.name).toBe("Fazenda Boa Vista");
    expect(profile.sources).toHaveLength(1);
  });
});

describe("renderProfileForAgent", () => {
  it("includes criteria fields and per-source status/data", () => {
    const profile = aggregateProfile(
      { name: "Fazenda Boa Vista", location: "Uberaba, MG", segment: "pecuária de corte" },
      [
        { source: "cnpj", status: "ok", data: { razaoSocial: "Boa Vista LTDA" }, fetchedAt: "now" },
        { source: "google", status: "not_configured", message: "sem chave", fetchedAt: "now" },
      ]
    );

    const text = renderProfileForAgent(profile);
    expect(text).toContain("Fazenda Boa Vista");
    expect(text).toContain("Uberaba, MG");
    expect(text).toContain("[CNPJ] status=ok");
    expect(text).toContain("Boa Vista LTDA");
    expect(text).toContain("[GOOGLE] status=not_configured");
    expect(text).toContain("sem chave");
  });
});
