import type { SearchCriteria, SourceResult } from "../types.js";
import { fetchCnpj } from "./cnpj.js";
import { fetchGoogle } from "./google.js";
import { fetchInstagram } from "./instagram.js";
import { fetchFacebook } from "./facebook.js";

/** Runs every data-source connector in parallel and returns their results as they settle. */
export async function fetchAllSources(criteria: SearchCriteria): Promise<SourceResult[]> {
  const results = await Promise.allSettled([
    fetchCnpj(criteria),
    fetchGoogle(criteria),
    fetchInstagram(criteria),
    fetchFacebook(criteria),
  ]);

  return results.map((r, i) => {
    if (r.status === "fulfilled") return r.value;
    const sourceNames = ["cnpj", "google", "instagram", "facebook"] as const;
    return {
      source: sourceNames[i],
      status: "error" as const,
      message: r.reason instanceof Error ? r.reason.message : "Erro desconhecido.",
      fetchedAt: new Date().toISOString(),
    };
  });
}
