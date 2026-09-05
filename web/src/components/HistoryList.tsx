import type { SearchRecord } from "../types";

interface Props {
  history: SearchRecord[];
  onSelect: (record: SearchRecord) => void;
}

export function HistoryList({ history, onSelect }: Props) {
  if (history.length === 0) return null;
  return (
    <div className="history-list">
      <h3>Buscas recentes</h3>
      <ul>
        {history.map((record) => (
          <li key={record.id}>
            <button onClick={() => onSelect(record)}>
              {record.criteria.name}{" "}
              <span className="history-date">
                {new Date(record.createdAt).toLocaleString("pt-BR")}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
