import type { GoogleData, SearchCriteria, SourceResult } from "../types.js";

/**
 * Runs a web search via the official Google Programmable Search Engine
 * (Custom Search JSON API). Requires GOOGLE_API_KEY and GOOGLE_CSE_ID.
 * Without those, this returns "not_configured" rather than falling back to
 * unofficial scraping.
 */
export async function fetchGoogle(criteria: SearchCriteria): Promise<SourceResult<GoogleData>> {
  const fetchedAt = new Date().toISOString();
  const apiKey = process.env.GOOGLE_API_KEY;
  const cseId = process.env.GOOGLE_CSE_ID;

  if (!apiKey || !cseId) {
    return {
      source: "google",
      status: "not_configured",
      message:
        "Defina GOOGLE_API_KEY e GOOGLE_CSE_ID (Google Programmable Search Engine) para habilitar esta fonte.",
      fetchedAt,
    };
  }

  const queryParts = [criteria.name, criteria.segment, criteria.location].filter(Boolean);
  const query = queryParts.join(" ");
  if (!query.trim()) {
    return {
      source: "google",
      status: "not_found",
      message: "Informe ao menos o nome do cliente para buscar no Google.",
      fetchedAt,
    };
  }

  try {
    const url = new URL("https://www.googleapis.com/customsearch/v1");
    url.searchParams.set("key", apiKey);
    url.searchParams.set("cx", cseId);
    url.searchParams.set("q", query);
    url.searchParams.set("num", "5");

    const res = await fetch(url);
    if (!res.ok) {
      const body = await res.text();
      return {
        source: "google",
        status: "error",
        message: `Google Custom Search retornou status ${res.status}: ${body.slice(0, 200)}`,
        fetchedAt,
      };
    }
    const json = (await res.json()) as {
      items?: Array<{ title: string; link: string; snippet: string }>;
    };
    const items = (json.items ?? []).map((item) => ({
      title: item.title,
      link: item.link,
      snippet: item.snippet,
    }));
    if (items.length === 0) {
      return { source: "google", status: "not_found", data: { items: [] }, fetchedAt };
    }
    return { source: "google", status: "ok", data: { items }, fetchedAt };
  } catch (err) {
    return {
      source: "google",
      status: "error",
      message: err instanceof Error ? err.message : "Falha ao consultar Google Custom Search.",
      fetchedAt,
    };
  }
}
