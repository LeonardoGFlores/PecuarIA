import type { Geometry } from "geojson";

export type { Geometry };

export type StatusEvidencia =
  | "observado"
  | "derivado"
  | "estimado"
  | "declarado"
  | "hipotese";

export type QualidadeEvidencia = "alta" | "media" | "baixa" | "insuficiente";

export interface Fazenda {
  id: string;
  nome: string;
  proprietario: string | null;
  geom: Geometry;
  area_total_ha: number | null;
  versao: number;
  fonte: string;
  status: StatusEvidencia;
  qualidade: QualidadeEvidencia;
}

export type TipoUso =
  | "pasto"
  | "mata"
  | "agua"
  | "lavoura"
  | "infraestrutura"
  | "outro";

export type SistemaProdutivo =
  | "corte"
  | "leite"
  | "agricultura"
  | "misto"
  | "nao_definido";

export interface AreaProdutiva {
  id: string;
  fazenda_id: string;
  nome: string;
  geom: Geometry;
  tipo_uso: TipoUso;
  area_ha: number | null;
  area_utilizavel_ha: number | null;
  sistema_produtivo: SistemaProdutivo;
  fonte: string;
  status: StatusEvidencia;
  qualidade: QualidadeEvidencia;
}

export type ToleranciaRisco = "baixa" | "media" | "alta";

export interface PerfilProdutorInput {
  objetivos: string[];
  capital_disponivel: number | null;
  limite_investimento: number | null;
  capital_giro: number | null;
  tolerancia_risco: ToleranciaRisco;
  disponibilidade_gestao_horas_semana: number | null;
}

export interface PerfilProdutor extends PerfilProdutorInput {
  id: string;
  fazenda_id: string;
}

export type ApoioTecnico = "proprio" | "contratado" | "nenhum";

export interface EquipeInput {
  quantidade_pessoas: number;
  funcoes: string[];
  disponibilidade_sazonal: Record<string, unknown> | null;
  competencias: string[];
  apoio_tecnico: ApoioTecnico;
}

export interface Equipe extends EquipeInput {
  id: string;
  fazenda_id: string;
}

export type TipoFornecedor = "animais" | "insumos" | "servicos" | "frete" | "comprador";

export interface FornecedorInput {
  nome: string;
  tipo: TipoFornecedor;
  regiao: string | null;
  contato: string | null;
  fonte: string;
}

export interface Fornecedor extends FornecedorInput {
  id: string;
}

export interface OfertaRegionalInput {
  fornecedor_id: string;
  categoria: string;
  especificacao: string | null;
  unidade: string;
  quantidade_disponivel: number | null;
  quantidade_minima: number | null;
  preco: number | null;
  condicoes: string | null;
  sazonalidade: string | null;
  data_registro: string;
  validade_cotacao: string | null;
  fonte: string;
}

export interface OfertaRegional extends OfertaRegionalInput {
  id: string;
  vencida: boolean;
}

export interface LogisticaOfertaInput {
  distancia_km: number | null;
  prazo_entrega_dias: number | null;
  custo_frete: number | null;
}

export interface LogisticaOferta extends LogisticaOfertaInput {
  id: string;
  oferta_id: string;
}
