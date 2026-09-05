import type { CustomerProfile, SearchCriteria, SourceResult } from "../types.js";

/** Combines the raw per-source results into one aggregated customer profile. */
export function aggregateProfile(criteria: SearchCriteria, sources: SourceResult[]): CustomerProfile {
  return { criteria, sources };
}

/** Renders the aggregated profile as plain text, ready to hand to the analysis agent. */
export function renderProfileForAgent(profile: CustomerProfile): string {
  const lines: string[] = [];
  lines.push(`Critérios de busca informados:`);
  lines.push(`- Nome: ${profile.criteria.name}`);
  if (profile.criteria.cnpj) lines.push(`- CNPJ: ${profile.criteria.cnpj}`);
  if (profile.criteria.location) lines.push(`- Localização: ${profile.criteria.location}`);
  if (profile.criteria.segment) lines.push(`- Segmento: ${profile.criteria.segment}`);
  if (profile.criteria.instagramHandle)
    lines.push(`- Instagram: @${profile.criteria.instagramHandle}`);
  if (profile.criteria.facebookPage) lines.push(`- Facebook: ${profile.criteria.facebookPage}`);
  if (profile.criteria.notes) lines.push(`- Observações: ${profile.criteria.notes}`);
  lines.push("");
  lines.push("Dados coletados por fonte:");

  for (const source of profile.sources) {
    lines.push(`\n[${source.source.toUpperCase()}] status=${source.status}`);
    if (source.message) lines.push(`  mensagem: ${source.message}`);
    if (source.data) lines.push(`  dados: ${JSON.stringify(source.data)}`);
  }

  return lines.join("\n");
}
