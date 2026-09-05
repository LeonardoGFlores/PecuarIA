import type { CnpjData, SearchCriteria, SourceResult } from "../types.js";

/**
 * Looks up a company's public registration data via BrasilAPI, a free public
 * mirror of Receita Federal's CNPJ registry. No API key required, but a real
 * CNPJ number must be supplied — there is no official free API for
 * searching CNPJ records by company name alone.
 */
export async function fetchCnpj(criteria: SearchCriteria): Promise<SourceResult<CnpjData>> {
  const fetchedAt = new Date().toISOString();
  const digits = criteria.cnpj?.replace(/\D/g, "");

  if (!digits) {
    return {
      source: "cnpj",
      status: "not_found",
      message: "Informe o CNPJ para consultar o registro oficial da empresa.",
      fetchedAt,
    };
  }

  if (digits.length !== 14) {
    return {
      source: "cnpj",
      status: "error",
      message: "CNPJ inválido: deve conter 14 dígitos.",
      fetchedAt,
    };
  }

  try {
    const res = await fetch(`https://brasilapi.com.br/api/cnpj/v1/${digits}`);
    if (res.status === 404) {
      return {
        source: "cnpj",
        status: "not_found",
        message: "CNPJ não encontrado no registro público.",
        fetchedAt,
      };
    }
    if (!res.ok) {
      return {
        source: "cnpj",
        status: "error",
        message: `BrasilAPI retornou status ${res.status}.`,
        fetchedAt,
      };
    }
    const json = (await res.json()) as Record<string, unknown>;
    const data: CnpjData = {
      cnpj: digits,
      razaoSocial: str(json.razao_social),
      nomeFantasia: str(json.nome_fantasia),
      situacao: str(json.descricao_situacao_cadastral),
      atividadePrincipal: str(
        Array.isArray(json.cnae_fiscal_descricao) ? undefined : json.cnae_fiscal_descricao
      ),
      municipio: str(json.municipio),
      uf: str(json.uf),
      capitalSocial:
        typeof json.capital_social === "number" ? json.capital_social : undefined,
      dataAbertura: str(json.data_inicio_atividade),
      socios: Array.isArray(json.qsa)
        ? (json.qsa as Array<Record<string, unknown>>)
            .map((s) => str(s.nome_socio))
            .filter((v): v is string => Boolean(v))
        : undefined,
    };
    return { source: "cnpj", status: "ok", data, fetchedAt };
  } catch (err) {
    return {
      source: "cnpj",
      status: "error",
      message: err instanceof Error ? err.message : "Falha ao consultar BrasilAPI.",
      fetchedAt,
    };
  }
}

function str(v: unknown): string | undefined {
  return typeof v === "string" && v.length > 0 ? v : undefined;
}
