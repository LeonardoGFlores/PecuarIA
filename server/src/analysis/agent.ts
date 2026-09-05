import Anthropic from "@anthropic-ai/sdk";
import type { AnalysisResult, CustomerProfile } from "../types.js";
import { renderProfileForAgent } from "./aggregator.js";

const MODEL = process.env.ANTHROPIC_MODEL ?? "claude-sonnet-5";

const SYSTEM_PROMPT = `Você é o agente interno de inteligência comercial da PecuarIA, uma empresa do
agronegócio (pecuária). Seu trabalho é ler os dados brutos coletados sobre um
potencial cliente (registro CNPJ, presença no Google, Instagram e Facebook) e
produzir duas coisas, sempre em português do Brasil:

1. Uma ANÁLISE DE PERFIL objetiva: quem é esse cliente, porte do negócio,
   sinais de atividade/engajamento nas redes, e nível de confiança dos dados
   (aponte explicitamente quando uma fonte não retornou dados ou não estava
   configurada — nunca invente informação que não veio dos dados fornecidos).
2. Uma ESTRATÉGIA DE ABORDAGEM prática para o time comercial: canal de
   contato recomendado, tom de comunicação, gancho/assunto inicial baseado em
   algo real dos dados, e próximos passos concretos.

Responda estritamente em JSON válido com o formato:
{"profileAnalysis": "...", "approachStrategy": "..."}
Sem markdown, sem texto fora do JSON.`;

export async function generateAnalysis(profile: CustomerProfile): Promise<AnalysisResult> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  const generatedAt = new Date().toISOString();

  if (!apiKey) {
    return {
      profileAnalysis:
        "Agente de análise não configurado: defina ANTHROPIC_API_KEY para gerar a análise automática do perfil.",
      approachStrategy:
        "Sem a chave de API configurada, nenhuma estratégia é gerada automaticamente. Revise os dados brutos coletados por fonte abaixo.",
      model: "none",
      generatedAt,
    };
  }

  const client = new Anthropic({ apiKey });
  const userContent = renderProfileForAgent(profile);

  const message = await client.messages.create({
    model: MODEL,
    max_tokens: 1500,
    system: SYSTEM_PROMPT,
    messages: [{ role: "user", content: userContent }],
  });

  const textBlock = message.content.find((b) => b.type === "text");
  const raw = textBlock && textBlock.type === "text" ? textBlock.text : "{}";

  let parsed: { profileAnalysis?: string; approachStrategy?: string };
  try {
    parsed = JSON.parse(raw);
  } catch {
    parsed = { profileAnalysis: raw, approachStrategy: "" };
  }

  return {
    profileAnalysis: parsed.profileAnalysis ?? "",
    approachStrategy: parsed.approachStrategy ?? "",
    model: MODEL,
    generatedAt,
  };
}
