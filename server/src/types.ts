/** Criteria the user fills in to define which customer profile to search for. */
export interface SearchCriteria {
  /** Person or company name to search for. */
  name: string;
  /** Brazilian CNPJ, digits only, if already known. */
  cnpj?: string;
  /** Instagram handle, without the leading @. */
  instagramHandle?: string;
  /** Facebook page name or ID. */
  facebookPage?: string;
  /** City/state/region, used to bias Google search results. */
  location?: string;
  /** Free-text description of the business segment (e.g. "pecuarista de corte"). */
  segment?: string;
  /** Extra free-text notes the user wants folded into the search query. */
  notes?: string;
}

export type SourceName = "cnpj" | "google" | "instagram" | "facebook";

export type SourceStatus = "ok" | "not_configured" | "not_found" | "error";

/** Uniform envelope every connector returns, regardless of source. */
export interface SourceResult<T = unknown> {
  source: SourceName;
  status: SourceStatus;
  message?: string;
  data?: T;
  fetchedAt: string;
}

export interface CnpjData {
  cnpj: string;
  razaoSocial?: string;
  nomeFantasia?: string;
  situacao?: string;
  atividadePrincipal?: string;
  municipio?: string;
  uf?: string;
  capitalSocial?: number;
  dataAbertura?: string;
  socios?: string[];
}

export interface GoogleResultItem {
  title: string;
  link: string;
  snippet: string;
}

export interface GoogleData {
  items: GoogleResultItem[];
}

export interface InstagramData {
  username: string;
  name?: string;
  biography?: string;
  followersCount?: number;
  mediaCount?: number;
  website?: string;
  recentCaptions?: string[];
}

export interface FacebookData {
  id: string;
  name: string;
  about?: string;
  category?: string;
  fanCount?: number;
  link?: string;
}

/** Aggregated view across all sources, built before handing off to the analysis agent. */
export interface CustomerProfile {
  criteria: SearchCriteria;
  sources: SourceResult[];
}

export interface AnalysisResult {
  /** Narrative profile summary written by the internal agent. */
  profileAnalysis: string;
  /** Recommended approach strategy for the sales/relationship team. */
  approachStrategy: string;
  /** Model used to generate the analysis, for auditability. */
  model: string;
  generatedAt: string;
}

export interface SearchRecord {
  id: number;
  criteria: SearchCriteria;
  sources: SourceResult[];
  analysis: AnalysisResult | null;
  createdAt: string;
}
