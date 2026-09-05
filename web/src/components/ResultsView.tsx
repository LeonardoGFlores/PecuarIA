import type { SearchRecord } from "../types";
import { SourceCard } from "./SourceCard";
import { AnalysisPanel } from "./AnalysisPanel";

export function ResultsView({ record }: { record: SearchRecord }) {
  return (
    <div className="results-view">
      <h2>Resultado para "{record.criteria.name}"</h2>
      {record.analysis && <AnalysisPanel analysis={record.analysis} />}
      <h3>Dados por fonte</h3>
      <div className="source-grid">
        {record.sources.map((s) => (
          <SourceCard key={s.source} result={s} />
        ))}
      </div>
    </div>
  );
}
