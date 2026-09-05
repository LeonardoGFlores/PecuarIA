import type { SourceResult } from "../types";

const SOURCE_LABELS: Record<string, string> = {
  cnpj: "CNPJ (Receita Federal / BrasilAPI)",
  google: "Google (Custom Search)",
  instagram: "Instagram",
  facebook: "Facebook",
};

const STATUS_LABELS: Record<string, string> = {
  ok: "OK",
  not_configured: "Não configurado",
  not_found: "Não encontrado",
  error: "Erro",
};

export function SourceCard({ result }: { result: SourceResult }) {
  return (
    <div className={`source-card status-${result.status}`}>
      <div className="source-card-header">
        <strong>{SOURCE_LABELS[result.source] ?? result.source}</strong>
        <span className="badge">{STATUS_LABELS[result.status] ?? result.status}</span>
      </div>
      {result.message && <p className="source-message">{result.message}</p>}
      {result.data && (
        <pre className="source-data">{JSON.stringify(result.data, null, 2)}</pre>
      )}
    </div>
  );
}
