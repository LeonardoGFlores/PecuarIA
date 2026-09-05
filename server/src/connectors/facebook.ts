import type { FacebookData, SearchCriteria, SourceResult } from "../types.js";

/**
 * Looks up a public Facebook Page via the official Graph API. Requires
 * FB_ACCESS_TOKEN (a token for an app with Page Public Content Access, or a
 * page access token for pages you manage). Direct page name/ID lookup is
 * used when facebookPage is provided; otherwise falls back to the
 * pages/search endpoint keyed on the customer name.
 */
export async function fetchFacebook(
  criteria: SearchCriteria
): Promise<SourceResult<FacebookData>> {
  const fetchedAt = new Date().toISOString();
  const accessToken = process.env.FB_ACCESS_TOKEN;

  if (!accessToken) {
    return {
      source: "facebook",
      status: "not_configured",
      message: "Defina FB_ACCESS_TOKEN (Facebook Graph API) para habilitar esta fonte.",
      fetchedAt,
    };
  }

  const target = criteria.facebookPage?.trim() || criteria.name.trim();
  if (!target) {
    return {
      source: "facebook",
      status: "not_found",
      message: "Informe o nome ou ID da página do Facebook do cliente.",
      fetchedAt,
    };
  }

  const fields = "id,name,about,category,fan_count,link";

  try {
    // If facebookPage looks like an explicit page name/ID, try a direct node lookup first.
    if (criteria.facebookPage) {
      const directUrl = new URL(`https://graph.facebook.com/v21.0/${encodeURIComponent(target)}`);
      directUrl.searchParams.set("fields", fields);
      directUrl.searchParams.set("access_token", accessToken);
      const directRes = await fetch(directUrl);
      const directJson = (await directRes.json()) as FacebookData & { error?: { message?: string } };
      if (directRes.ok && !directJson.error) {
        return { source: "facebook", status: "ok", data: directJson, fetchedAt };
      }
    }

    const searchUrl = new URL("https://graph.facebook.com/v21.0/pages/search");
    searchUrl.searchParams.set("q", target);
    searchUrl.searchParams.set("fields", fields);
    searchUrl.searchParams.set("access_token", accessToken);

    const res = await fetch(searchUrl);
    const json = (await res.json()) as {
      data?: FacebookData[];
      error?: { message?: string };
    };

    if (!res.ok || json.error) {
      return {
        source: "facebook",
        status: "error",
        message: json.error?.message ?? `Graph API retornou status ${res.status}.`,
        fetchedAt,
      };
    }

    const best = json.data?.[0];
    if (!best) {
      return {
        source: "facebook",
        status: "not_found",
        message: "Nenhuma página encontrada com esse nome.",
        fetchedAt,
      };
    }

    return { source: "facebook", status: "ok", data: best, fetchedAt };
  } catch (err) {
    return {
      source: "facebook",
      status: "error",
      message: err instanceof Error ? err.message : "Falha ao consultar Facebook Graph API.",
      fetchedAt,
    };
  }
}
