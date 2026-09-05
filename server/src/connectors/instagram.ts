import type { InstagramData, SearchCriteria, SourceResult } from "../types.js";

/**
 * Looks up a public Instagram Business/Creator profile via the official
 * Instagram Graph API "Business Discovery" edge. This only works for
 * accounts that are themselves Business/Creator accounts (Instagram does
 * not expose an API for searching arbitrary personal profiles), and
 * requires the calling app to have its own connected IG Business Account
 * and a valid access token. Requires IG_BUSINESS_ACCOUNT_ID and
 * IG_ACCESS_TOKEN.
 */
export async function fetchInstagram(
  criteria: SearchCriteria
): Promise<SourceResult<InstagramData>> {
  const fetchedAt = new Date().toISOString();
  const igBusinessAccountId = process.env.IG_BUSINESS_ACCOUNT_ID;
  const accessToken = process.env.IG_ACCESS_TOKEN;

  if (!igBusinessAccountId || !accessToken) {
    return {
      source: "instagram",
      status: "not_configured",
      message:
        "Defina IG_BUSINESS_ACCOUNT_ID e IG_ACCESS_TOKEN (Instagram Graph API - Business Discovery) para habilitar esta fonte.",
      fetchedAt,
    };
  }

  const username = criteria.instagramHandle?.replace(/^@/, "").trim();
  if (!username) {
    return {
      source: "instagram",
      status: "not_found",
      message: "Informe o @ do Instagram do cliente.",
      fetchedAt,
    };
  }

  try {
    const fields = `business_discovery.username(${username}){username,name,biography,followers_count,media_count,website,media.limit(5){caption}}`;
    const url = new URL(
      `https://graph.facebook.com/v21.0/${igBusinessAccountId}`
    );
    url.searchParams.set("fields", fields);
    url.searchParams.set("access_token", accessToken);

    const res = await fetch(url);
    const json = (await res.json()) as {
      business_discovery?: {
        username: string;
        name?: string;
        biography?: string;
        followers_count?: number;
        media_count?: number;
        website?: string;
        media?: { data?: Array<{ caption?: string }> };
      };
      error?: { message?: string };
    };

    if (!res.ok || json.error) {
      return {
        source: "instagram",
        status: "error",
        message: json.error?.message ?? `Graph API retornou status ${res.status}.`,
        fetchedAt,
      };
    }

    const bd = json.business_discovery;
    if (!bd) {
      return {
        source: "instagram",
        status: "not_found",
        message: "Perfil não encontrado ou não é uma conta comercial/criador pública.",
        fetchedAt,
      };
    }

    const data: InstagramData = {
      username: bd.username,
      name: bd.name,
      biography: bd.biography,
      followersCount: bd.followers_count,
      mediaCount: bd.media_count,
      website: bd.website,
      recentCaptions: (bd.media?.data ?? [])
        .map((m) => m.caption)
        .filter((c): c is string => Boolean(c)),
    };
    return { source: "instagram", status: "ok", data, fetchedAt };
  } catch (err) {
    return {
      source: "instagram",
      status: "error",
      message: err instanceof Error ? err.message : "Falha ao consultar Instagram Graph API.",
      fetchedAt,
    };
  }
}
