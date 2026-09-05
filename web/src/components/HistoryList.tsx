import type { SearchRecord } from "../types";

interface Props {
  history: SearchRecord[];
  selectedId?: number;
  onSelect: (record: SearchRecord) => void;
}

export function HistoryList({ history, selectedId, onSelect }: Props) {
  if (history.length === 0) return null;
  return (
    <nav className="history-list" aria-label="Buscas recentes">
      <h3>Buscas recentes</h3>
      <ul>
        {history.map((record) => (
          <li key={record.id}>
            <button
              onClick={() => onSelect(record)}
              aria-current={record.id === selectedId ? "true" : undefined}
              className={record.id === selectedId ? "history-item-active" : undefined}
            >
              {record.criteria.name}{" "}
              <span className="history-date">
                {new Date(record.createdAt).toLocaleString("pt-BR")}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
