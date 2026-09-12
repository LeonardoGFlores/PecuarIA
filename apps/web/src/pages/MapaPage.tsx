import { useEffect, useState } from "react";
import { listarAreasProdutivas, listarFazendas } from "../api/client";
import type { AreaProdutiva, Fazenda } from "../api/types";
import { FarmMap } from "../components/map/FarmMap";

export function MapaPage() {
  const [fazendas, setFazendas] = useState<Fazenda[]>([]);
  const [areasPorFazenda, setAreasPorFazenda] = useState<Record<string, AreaProdutiva[]>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    let cancelado = false;

    async function carregar() {
      try {
        const listaFazendas = await listarFazendas();
        if (cancelado) return;
        setFazendas(listaFazendas);

        const entradas = await Promise.all(
          listaFazendas.map(async (fazenda) => [fazenda.id, await listarAreasProdutivas(fazenda.id)] as const),
        );
        if (cancelado) return;
        setAreasPorFazenda(Object.fromEntries(entradas));
      } catch (e) {
        if (!cancelado) setErro(e instanceof Error ? e.message : "Erro ao carregar dados da API");
      } finally {
        if (!cancelado) setCarregando(false);
      }
    }

    carregar();
    return () => {
      cancelado = true;
    };
  }, []);

  return (
    <div className="mapa-page">
      {erro && (
        <div className="banner-erro">
          Não foi possível carregar dados da API ({erro}). Verifique se a API está rodando em{" "}
          {import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}.
        </div>
      )}
      {!erro && !carregando && fazendas.length === 0 && (
        <div className="banner-info">Nenhuma fazenda cadastrada ainda. Use a API para criar a primeira.</div>
      )}
      <div className="mapa-container">
        <FarmMap fazendas={fazendas} areasPorFazenda={areasPorFazenda} />
      </div>
    </div>
  );
}
