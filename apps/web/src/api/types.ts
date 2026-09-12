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
