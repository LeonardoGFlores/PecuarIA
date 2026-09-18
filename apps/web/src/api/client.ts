import type {
  AreaProdutiva,
  Equipe,
  EquipeInput,
  Fazenda,
  Fornecedor,
  FornecedorInput,
  LogisticaOferta,
  LogisticaOfertaInput,
  OfertaRegional,
  OfertaRegionalInput,
  PerfilProdutor,
  PerfilProdutorInput,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new ApiError(response.status, `Falha ao buscar ${path}: HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function post<T>(path: string, corpo: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  if (!response.ok) {
    throw new ApiError(response.status, `Falha ao criar ${path}: HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function put<T>(path: string, corpo: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  if (!response.ok) {
    throw new ApiError(response.status, `Falha ao atualizar ${path}: HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function del(path: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "DELETE" });
  if (!response.ok) {
    throw new ApiError(response.status, `Falha ao remover ${path}: HTTP ${response.status}`);
  }
}

export function listarFazendas(): Promise<Fazenda[]> {
  return get<Fazenda[]>("/fazendas");
}

export function listarAreasProdutivas(fazendaId: string): Promise<AreaProdutiva[]> {
  return get<AreaProdutiva[]>(`/fazendas/${fazendaId}/areas-produtivas`);
}

export function obterPerfilProdutor(fazendaId: string): Promise<PerfilProdutor> {
  return get<PerfilProdutor>(`/fazendas/${fazendaId}/perfil-produtor`);
}

export function criarPerfilProdutor(fazendaId: string, dados: PerfilProdutorInput): Promise<PerfilProdutor> {
  return post<PerfilProdutor>(`/fazendas/${fazendaId}/perfil-produtor`, dados);
}

export function atualizarPerfilProdutor(fazendaId: string, dados: PerfilProdutorInput): Promise<PerfilProdutor> {
  return put<PerfilProdutor>(`/fazendas/${fazendaId}/perfil-produtor`, dados);
}

export function obterEquipe(fazendaId: string): Promise<Equipe> {
  return get<Equipe>(`/fazendas/${fazendaId}/equipe`);
}

export function criarEquipe(fazendaId: string, dados: EquipeInput): Promise<Equipe> {
  return post<Equipe>(`/fazendas/${fazendaId}/equipe`, dados);
}

export function atualizarEquipe(fazendaId: string, dados: EquipeInput): Promise<Equipe> {
  return put<Equipe>(`/fazendas/${fazendaId}/equipe`, dados);
}

export function listarFornecedores(): Promise<Fornecedor[]> {
  return get<Fornecedor[]>("/fontes/fornecedores");
}

export function criarFornecedor(dados: FornecedorInput): Promise<Fornecedor> {
  return post<Fornecedor>("/fontes/fornecedores", dados);
}

export function atualizarFornecedor(fornecedorId: string, dados: FornecedorInput): Promise<Fornecedor> {
  return put<Fornecedor>(`/fontes/fornecedores/${fornecedorId}`, dados);
}

export function removerFornecedor(fornecedorId: string): Promise<void> {
  return del(`/fontes/fornecedores/${fornecedorId}`);
}

export function listarOfertas(fornecedorId?: string): Promise<OfertaRegional[]> {
  const query = fornecedorId ? `?fornecedor_id=${fornecedorId}` : "";
  return get<OfertaRegional[]>(`/fontes/ofertas${query}`);
}

export function criarOferta(dados: OfertaRegionalInput): Promise<OfertaRegional> {
  return post<OfertaRegional>("/fontes/ofertas", dados);
}

export function atualizarOferta(ofertaId: string, dados: OfertaRegionalInput): Promise<OfertaRegional> {
  return put<OfertaRegional>(`/fontes/ofertas/${ofertaId}`, dados);
}

export function removerOferta(ofertaId: string): Promise<void> {
  return del(`/fontes/ofertas/${ofertaId}`);
}

export function listarLogistica(ofertaId: string): Promise<LogisticaOferta[]> {
  return get<LogisticaOferta[]>(`/fontes/ofertas/${ofertaId}/logistica`);
}

export function criarLogistica(ofertaId: string, dados: LogisticaOfertaInput): Promise<LogisticaOferta> {
  return post<LogisticaOferta>(`/fontes/ofertas/${ofertaId}/logistica`, dados);
}

export function removerLogistica(logisticaId: string): Promise<void> {
  return del(`/fontes/logistica/${logisticaId}`);
}
