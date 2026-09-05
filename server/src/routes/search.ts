import { Router } from "express";
import { z } from "zod";
import { fetchAllSources } from "../connectors/index.js";
import { aggregateProfile } from "../analysis/aggregator.js";
import { generateAnalysis } from "../analysis/agent.js";
import { getSearch, insertSearch, listSearches } from "../db.js";

const router = Router();

const criteriaSchema = z.object({
  name: z.string().min(1, "Informe o nome do cliente."),
  cnpj: z.string().optional(),
  instagramHandle: z.string().optional(),
  facebookPage: z.string().optional(),
  location: z.string().optional(),
  segment: z.string().optional(),
  notes: z.string().optional(),
});

router.post("/search", async (req, res) => {
  const parsed = criteriaSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.flatten() });
  }
  const criteria = parsed.data;

  try {
    const sources = await fetchAllSources(criteria);
    const profile = aggregateProfile(criteria, sources);
    const analysis = await generateAnalysis(profile);
    const record = insertSearch({ criteria, sources, analysis });
    res.json(record);
  } catch (err) {
    res.status(500).json({
      error: err instanceof Error ? err.message : "Erro inesperado ao processar a busca.",
    });
  }
});

router.get("/searches", (_req, res) => {
  res.json(listSearches());
});

router.get("/searches/:id", (req, res) => {
  const id = Number(req.params.id);
  if (!Number.isInteger(id)) {
    return res.status(400).json({ error: "ID inválido." });
  }
  const record = getSearch(id);
  if (!record) return res.status(404).json({ error: "Busca não encontrada." });
  res.json(record);
});

export default router;
