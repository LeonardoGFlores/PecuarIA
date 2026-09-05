import { useState } from "react";
import type { SearchCriteria } from "../types";

interface Props {
  loading: boolean;
  onSubmit: (criteria: SearchCriteria) => void;
}

const emptyCriteria: SearchCriteria = {
  name: "",
  cnpj: "",
  instagramHandle: "",
  facebookPage: "",
  location: "",
  segment: "",
  notes: "",
};

export function SearchForm({ loading, onSubmit }: Props) {
  const [criteria, setCriteria] = useState<SearchCriteria>(emptyCriteria);

  function update<K extends keyof SearchCriteria>(key: K, value: string) {
    setCriteria((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!criteria.name.trim()) return;
    const cleaned: SearchCriteria = Object.fromEntries(
      Object.entries(criteria).filter(([, v]) => v && v.trim() !== "")
    ) as SearchCriteria;
    onSubmit(cleaned);
  }

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <h2>Definir perfil do cliente</h2>
      <div className="field">
        <label htmlFor="name">Nome / Razão social *</label>
        <input
          id="name"
          value={criteria.name}
          onChange={(e) => update("name", e.target.value)}
          placeholder="Fazenda Boa Vista"
          required
        />
      </div>
      <div className="grid-2">
        <div className="field">
          <label htmlFor="cnpj">CNPJ</label>
          <input
            id="cnpj"
            value={criteria.cnpj}
            onChange={(e) => update("cnpj", e.target.value)}
            placeholder="00.000.000/0001-00"
          />
        </div>
        <div className="field">
          <label htmlFor="location">Localização</label>
          <input
            id="location"
            value={criteria.location}
            onChange={(e) => update("location", e.target.value)}
            placeholder="Uberaba, MG"
          />
        </div>
      </div>
      <div className="grid-2">
        <div className="field">
          <label htmlFor="instagram">Instagram (@)</label>
          <input
            id="instagram"
            value={criteria.instagramHandle}
            onChange={(e) => update("instagramHandle", e.target.value)}
            placeholder="fazendaboavista"
          />
        </div>
        <div className="field">
          <label htmlFor="facebook">Página do Facebook</label>
          <input
            id="facebook"
            value={criteria.facebookPage}
            onChange={(e) => update("facebookPage", e.target.value)}
            placeholder="Fazenda Boa Vista"
          />
        </div>
      </div>
      <div className="field">
        <label htmlFor="segment">Segmento</label>
        <input
          id="segment"
          value={criteria.segment}
          onChange={(e) => update("segment", e.target.value)}
          placeholder="pecuária de corte, confinamento..."
        />
      </div>
      <div className="field">
        <label htmlFor="notes">Observações</label>
        <textarea
          id="notes"
          value={criteria.notes}
          onChange={(e) => update("notes", e.target.value)}
          placeholder="Qualquer contexto adicional relevante"
          rows={3}
        />
      </div>
      <button type="submit" disabled={loading}>
        {loading ? "Buscando..." : "Buscar cliente"}
      </button>
    </form>
  );
}
