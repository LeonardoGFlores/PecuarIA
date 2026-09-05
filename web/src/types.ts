export interface SearchCriteria {
  name: string;
  cnpj?: string;
  instagramHandle?: string;
  facebookPage?: string;
  location?: string;
  segment?: string;
  notes?: string;
}

export type SourceName = "cnpj" | "google" | "instagram" | "facebook";
export type SourceStatus = "ok" | "not_configured" | "not_found" | "error";

export interface SourceResult<T = Record<string, unknown>> {
  source: SourceName;
  status: SourceStatus;
  message?: string;
  data?: T;
  fetchedAt: string;
}

export interface AnalysisResult {
  profileAnalysis: string;
  approachStrategy: string;
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
