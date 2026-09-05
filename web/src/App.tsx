import { useEffect, useState } from "react";
import type { SearchCriteria, SearchRecord } from "./types";
import { fetchHistory, runSearch } from "./api";
import { SearchForm } from "./components/SearchForm";
import { ResultsView } from "./components/ResultsView";
import { HistoryList } from "./components/HistoryList";

export default function App() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState<SearchRecord | null>(null);
  const [history, setHistory] = useState<SearchRecord[]>([]);

  useEffect(() => {
    fetchHistory().then(setHistory).catch(() => undefined);
  }, []);

  async function handleSubmit(criteria: SearchCriteria) {
    setLoading(true);
    setError(null);
    try {
      const record = await runSearch(criteria);
      setCurrent(record);
      setHistory((prev) => [record, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao buscar cliente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>PecuarIA — Busca e Análise de Clientes</h1>
        <p className="subtitle">
          Defina o perfil e o sistema pesquisa CNPJ, Google, Instagram e Facebook, gera a
          análise do perfil e uma estratégia de abordagem.
        </p>
      </header>
      <main>
        <div className="sidebar">
          <SearchForm loading={loading} onSubmit={handleSubmit} />
          <HistoryList history={history} selectedId={current?.id} onSelect={setCurrent} />
        </div>
        <div className="content" aria-live="polite">
          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
          {current ? (
            <ResultsView record={current} />
          ) : (
            <p className="empty-state">
              {loading
                ? "Buscando cliente nas fontes configuradas..."
                : 'Preencha o perfil ao lado e clique em "Buscar cliente" para iniciar.'}
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
