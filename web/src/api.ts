import type { SearchCriteria, SearchRecord } from "./types";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ? JSON.stringify(body.error) : `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function runSearch(criteria: SearchCriteria): Promise<SearchRecord> {
  const res = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(criteria),
  });
  return handle<SearchRecord>(res);
}

export async function fetchHistory(): Promise<SearchRecord[]> {
  const res = await fetch("/api/searches");
  return handle<SearchRecord[]>(res);
}
