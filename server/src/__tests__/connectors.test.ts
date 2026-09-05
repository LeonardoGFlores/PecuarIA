import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchCnpj } from "../connectors/cnpj.js";
import { fetchGoogle } from "../connectors/google.js";
import { fetchInstagram } from "../connectors/instagram.js";
import { fetchFacebook } from "../connectors/facebook.js";

const originalEnv = { ...process.env };
const originalFetch = global.fetch;

beforeEach(() => {
  process.env = { ...originalEnv };
});

afterEach(() => {
  global.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe("fetchCnpj", () => {
  it("returns not_found status when no CNPJ is provided", async () => {
    const result = await fetchCnpj({ name: "Fazenda Boa Vista" });
    expect(result.status).toBe("not_found");
  });

  it("returns error status for malformed CNPJ", async () => {
    const result = await fetchCnpj({ name: "x", cnpj: "123" });
    expect(result.status).toBe("error");
  });

  it("parses a successful BrasilAPI response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        razao_social: "Boa Vista Agropecuaria LTDA",
        nome_fantasia: "Boa Vista",
        descricao_situacao_cadastral: "ATIVA",
        cnae_fiscal_descricao: "Criação de bovinos",
        municipio: "Uberaba",
        uf: "MG",
        capital_social: 500000,
        data_inicio_atividade: "2010-01-01",
        qsa: [{ nome_socio: "João da Silva" }],
      }),
    }) as unknown as typeof fetch;

    const result = await fetchCnpj({ name: "x", cnpj: "12.345.678/0001-90" });
    expect(result.status).toBe("ok");
    expect(result.data?.razaoSocial).toBe("Boa Vista Agropecuaria LTDA");
    expect(result.data?.socios).toEqual(["João da Silva"]);
  });

  it("maps a 404 to not_found", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 }) as unknown as typeof fetch;
    const result = await fetchCnpj({ name: "x", cnpj: "12345678000190" });
    expect(result.status).toBe("not_found");
  });
});

describe("fetchGoogle", () => {
  it("returns not_configured when API keys are missing", async () => {
    delete process.env.GOOGLE_API_KEY;
    delete process.env.GOOGLE_CSE_ID;
    const result = await fetchGoogle({ name: "Fazenda Boa Vista" });
    expect(result.status).toBe("not_configured");
  });

  it("returns parsed items when configured", async () => {
    process.env.GOOGLE_API_KEY = "key";
    process.env.GOOGLE_CSE_ID = "cse";
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [{ title: "t", link: "https://x.com", snippet: "s" }],
      }),
    }) as unknown as typeof fetch;

    const result = await fetchGoogle({ name: "Fazenda Boa Vista" });
    expect(result.status).toBe("ok");
    expect(result.data?.items).toHaveLength(1);
  });
});

describe("fetchInstagram", () => {
  it("returns not_configured when credentials are missing", async () => {
    delete process.env.IG_BUSINESS_ACCOUNT_ID;
    delete process.env.IG_ACCESS_TOKEN;
    const result = await fetchInstagram({ name: "x", instagramHandle: "fazendaboavista" });
    expect(result.status).toBe("not_configured");
  });
});

describe("fetchFacebook", () => {
  it("returns not_configured when access token is missing", async () => {
    delete process.env.FB_ACCESS_TOKEN;
    const result = await fetchFacebook({ name: "Fazenda Boa Vista" });
    expect(result.status).toBe("not_configured");
  });
});
