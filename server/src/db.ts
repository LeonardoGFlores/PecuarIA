import Database from "better-sqlite3";
import path from "node:path";
import fs from "node:fs";
import type { AnalysisResult, SearchCriteria, SearchRecord, SourceResult } from "./types.js";

const dataDir = path.resolve(process.cwd(), "data");
fs.mkdirSync(dataDir, { recursive: true });

const db = new Database(path.join(dataDir, "pecuaria.sqlite"));
db.pragma("journal_mode = WAL");

db.exec(`
  CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    criteria_json TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    analysis_json TEXT,
    created_at TEXT NOT NULL
  );
`);

interface InsertSearchInput {
  criteria: SearchCriteria;
  sources: SourceResult[];
  analysis: AnalysisResult | null;
}

export function insertSearch(input: InsertSearchInput): SearchRecord {
  const createdAt = new Date().toISOString();
  const stmt = db.prepare(
    `INSERT INTO searches (criteria_json, sources_json, analysis_json, created_at)
     VALUES (@criteria_json, @sources_json, @analysis_json, @created_at)`
  );
  const result = stmt.run({
    criteria_json: JSON.stringify(input.criteria),
    sources_json: JSON.stringify(input.sources),
    analysis_json: input.analysis ? JSON.stringify(input.analysis) : null,
    created_at: createdAt,
  });
  return {
    id: Number(result.lastInsertRowid),
    criteria: input.criteria,
    sources: input.sources,
    analysis: input.analysis,
    createdAt,
  };
}

interface SearchRow {
  id: number;
  criteria_json: string;
  sources_json: string;
  analysis_json: string | null;
  created_at: string;
}

function rowToRecord(row: SearchRow): SearchRecord {
  return {
    id: row.id,
    criteria: JSON.parse(row.criteria_json),
    sources: JSON.parse(row.sources_json),
    analysis: row.analysis_json ? JSON.parse(row.analysis_json) : null,
    createdAt: row.created_at,
  };
}

export function listSearches(limit = 50): SearchRecord[] {
  const rows = db
    .prepare(`SELECT * FROM searches ORDER BY id DESC LIMIT ?`)
    .all(limit) as SearchRow[];
  return rows.map(rowToRecord);
}

export function getSearch(id: number): SearchRecord | undefined {
  const row = db.prepare(`SELECT * FROM searches WHERE id = ?`).get(id) as
    | SearchRow
    | undefined;
  return row ? rowToRecord(row) : undefined;
}

export default db;
