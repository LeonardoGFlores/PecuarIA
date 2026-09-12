import type { AreaProdutiva, Fazenda } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Falha ao buscar ${path}: HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function listarFazendas(): Promise<Fazenda[]> {
  return get<Fazenda[]>("/fazendas");
}

export function listarAreasProdutivas(fazendaId: string): Promise<AreaProdutiva[]> {
  return get<AreaProdutiva[]>(`/fazendas/${fazendaId}/areas-produtivas`);
}
