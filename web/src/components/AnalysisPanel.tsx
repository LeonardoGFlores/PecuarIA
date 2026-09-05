import type { AnalysisResult } from "../types";

export function AnalysisPanel({ analysis }: { analysis: AnalysisResult }) {
  return (
    <div className="analysis-panel">
      <h3>Análise do perfil</h3>
      <p>{analysis.profileAnalysis}</p>
      <h3>Estratégia de abordagem</h3>
      <p>{analysis.approachStrategy}</p>
      <p className="analysis-meta">
        Gerado por {analysis.model} em {new Date(analysis.generatedAt).toLocaleString("pt-BR")}
      </p>
    </div>
  );
}
