import { type FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  atualizarEquipe,
  atualizarPerfilProdutor,
  criarEquipe,
  criarPerfilProdutor,
  listarFazendas,
  obterEquipe,
  obterPerfilProdutor,
} from "../api/client";
import type {
  ApoioTecnico,
  EquipeInput,
  Fazenda,
  PerfilProdutorInput,
  ToleranciaRisco,
} from "../api/types";

const PERFIL_VAZIO: PerfilProdutorInput = {
  objetivos: [],
  capital_disponivel: null,
  limite_investimento: null,
  capital_giro: null,
  tolerancia_risco: "media",
  disponibilidade_gestao_horas_semana: null,
};

const EQUIPE_VAZIA: EquipeInput = {
  quantidade_pessoas: 0,
  funcoes: [],
  disponibilidade_sazonal: null,
  competencias: [],
  apoio_tecnico: "nenhum",
};

function listaParaTexto(lista: string[]): string {
  return lista.join(", ");
}

function textoParaLista(texto: string): string[] {
  return texto
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function PerfilPage() {
  const [fazendas, setFazendas] = useState<Fazenda[]>([]);
  const [fazendaId, setFazendaId] = useState<string>("");
  const [carregandoFazendas, setCarregandoFazendas] = useState(true);
  const [erroFazendas, setErroFazendas] = useState<string | null>(null);

  const [perfil, setPerfil] = useState<PerfilProdutorInput>(PERFIL_VAZIO);
  const [perfilExiste, setPerfilExiste] = useState(false);
  const [equipe, setEquipe] = useState<EquipeInput>(EQUIPE_VAZIA);
  const [equipeExiste, setEquipeExiste] = useState(false);
  const [disponibilidadeSazonalTexto, setDisponibilidadeSazonalTexto] = useState("");

  const [erro, setErro] = useState<string | null>(null);
  const [mensagem, setMensagem] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    listarFazendas()
      .then((lista) => {
        if (cancelado) return;
        setFazendas(lista);
        if (lista.length > 0) setFazendaId(lista[0].id);
      })
      .catch((e) => {
        if (!cancelado) setErroFazendas(e instanceof Error ? e.message : "Erro ao carregar fazendas");
      })
      .finally(() => {
        if (!cancelado) setCarregandoFazendas(false);
      });
    return () => {
      cancelado = true;
    };
  }, []);

  useEffect(() => {
    if (!fazendaId) return;
    let cancelado = false;
    setErro(null);
    setMensagem(null);

    obterPerfilProdutor(fazendaId)
      .then((dados) => {
        if (cancelado) return;
        setPerfil(dados);
        setPerfilExiste(true);
      })
      .catch((e) => {
        if (cancelado) return;
        if (e instanceof ApiError && e.status === 404) {
          setPerfil(PERFIL_VAZIO);
          setPerfilExiste(false);
        } else {
          setErro(e instanceof Error ? e.message : "Erro ao carregar perfil do produtor");
        }
      });

    obterEquipe(fazendaId)
      .then((dados) => {
        if (cancelado) return;
        setEquipe(dados);
        setEquipeExiste(true);
        setDisponibilidadeSazonalTexto(dados.disponibilidade_sazonal ? JSON.stringify(dados.disponibilidade_sazonal) : "");
      })
      .catch((e) => {
        if (cancelado) return;
        if (e instanceof ApiError && e.status === 404) {
          setEquipe(EQUIPE_VAZIA);
          setEquipeExiste(false);
          setDisponibilidadeSazonalTexto("");
        } else {
          setErro(e instanceof Error ? e.message : "Erro ao carregar equipe");
        }
      });

    return () => {
      cancelado = true;
    };
  }, [fazendaId]);

  async function salvarPerfil(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setMensagem(null);
    try {
      const salvo = perfilExiste
        ? await atualizarPerfilProdutor(fazendaId, perfil)
        : await criarPerfilProdutor(fazendaId, perfil);
      setPerfil(salvo);
      setPerfilExiste(true);
      setMensagem("Perfil do produtor salvo.");
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar perfil do produtor");
    }
  }

  async function salvarEquipe(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setMensagem(null);

    let disponibilidadeSazonal: Record<string, unknown> | null = null;
    if (disponibilidadeSazonalTexto.trim() !== "") {
      try {
        disponibilidadeSazonal = JSON.parse(disponibilidadeSazonalTexto);
      } catch {
        setErro("Disponibilidade sazonal precisa ser um JSON válido (ou deixe em branco).");
        return;
      }
    }

    const dados: EquipeInput = { ...equipe, disponibilidade_sazonal: disponibilidadeSazonal };
    try {
      const salvo = equipeExiste ? await atualizarEquipe(fazendaId, dados) : await criarEquipe(fazendaId, dados);
      setEquipe(salvo);
      setEquipeExiste(true);
      setMensagem("Equipe salva.");
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar equipe");
    }
  }

  return (
    <div className="crud-page">
      <h1>Perfil operacional</h1>
      <p>Produtor, equipe, infraestrutura e capital.</p>

      {erroFazendas && <div className="banner-erro">Não foi possível carregar fazendas ({erroFazendas}).</div>}
      {!carregandoFazendas && fazendas.length === 0 && (
        <div className="banner-info">Nenhuma fazenda cadastrada ainda. Use a API para criar a primeira.</div>
      )}

      {fazendas.length > 0 && (
        <>
          <label className="form-field">
            Fazenda
            <select value={fazendaId} onChange={(evento) => setFazendaId(evento.target.value)}>
              {fazendas.map((fazenda) => (
                <option key={fazenda.id} value={fazenda.id}>
                  {fazenda.nome}
                </option>
              ))}
            </select>
          </label>

          {erro && <div className="banner-erro">{erro}</div>}
          {mensagem && <div className="banner-info">{mensagem}</div>}

          <form className="form-grid" onSubmit={salvarPerfil}>
            <h2>Perfil do produtor {!perfilExiste && <span className="badge-pendente">ainda não cadastrado</span>}</h2>
            <label>
              Objetivos (separados por vírgula)
              <input
                value={listaParaTexto(perfil.objetivos)}
                onChange={(evento) => setPerfil({ ...perfil, objetivos: textoParaLista(evento.target.value) })}
              />
            </label>
            <label>
              Capital disponível
              <input
                type="number"
                min={0}
                step="0.01"
                value={perfil.capital_disponivel ?? ""}
                onChange={(evento) =>
                  setPerfil({ ...perfil, capital_disponivel: evento.target.value === "" ? null : Number(evento.target.value) })
                }
              />
            </label>
            <label>
              Limite de investimento
              <input
                type="number"
                min={0}
                step="0.01"
                value={perfil.limite_investimento ?? ""}
                onChange={(evento) =>
                  setPerfil({ ...perfil, limite_investimento: evento.target.value === "" ? null : Number(evento.target.value) })
                }
              />
            </label>
            <label>
              Capital de giro
              <input
                type="number"
                min={0}
                step="0.01"
                value={perfil.capital_giro ?? ""}
                onChange={(evento) =>
                  setPerfil({ ...perfil, capital_giro: evento.target.value === "" ? null : Number(evento.target.value) })
                }
              />
            </label>
            <label>
              Tolerância a risco
              <select
                value={perfil.tolerancia_risco}
                onChange={(evento) => setPerfil({ ...perfil, tolerancia_risco: evento.target.value as ToleranciaRisco })}
              >
                <option value="baixa">Baixa</option>
                <option value="media">Média</option>
                <option value="alta">Alta</option>
              </select>
            </label>
            <label>
              Disponibilidade de gestão (horas/semana)
              <input
                type="number"
                min={0}
                max={168}
                step="0.5"
                value={perfil.disponibilidade_gestao_horas_semana ?? ""}
                onChange={(evento) =>
                  setPerfil({
                    ...perfil,
                    disponibilidade_gestao_horas_semana: evento.target.value === "" ? null : Number(evento.target.value),
                  })
                }
              />
            </label>
            <button type="submit">{perfilExiste ? "Atualizar perfil" : "Cadastrar perfil"}</button>
          </form>

          <form className="form-grid" onSubmit={salvarEquipe}>
            <h2>Equipe {!equipeExiste && <span className="badge-pendente">ainda não cadastrada</span>}</h2>
            <label>
              Quantidade de pessoas
              <input
                type="number"
                min={0}
                value={equipe.quantidade_pessoas}
                onChange={(evento) => setEquipe({ ...equipe, quantidade_pessoas: Number(evento.target.value) })}
              />
            </label>
            <label>
              Funções (separadas por vírgula)
              <input
                value={listaParaTexto(equipe.funcoes)}
                onChange={(evento) => setEquipe({ ...equipe, funcoes: textoParaLista(evento.target.value) })}
              />
            </label>
            <label>
              Competências (separadas por vírgula)
              <input
                value={listaParaTexto(equipe.competencias)}
                onChange={(evento) => setEquipe({ ...equipe, competencias: textoParaLista(evento.target.value) })}
              />
            </label>
            <label>
              Apoio técnico
              <select
                value={equipe.apoio_tecnico}
                onChange={(evento) => setEquipe({ ...equipe, apoio_tecnico: evento.target.value as ApoioTecnico })}
              >
                <option value="proprio">Próprio</option>
                <option value="contratado">Contratado</option>
                <option value="nenhum">Nenhum</option>
              </select>
            </label>
            <label>
              Disponibilidade sazonal (JSON, opcional)
              <textarea
                rows={3}
                placeholder='{"seca": "baixa", "chuvas": "alta"}'
                value={disponibilidadeSazonalTexto}
                onChange={(evento) => setDisponibilidadeSazonalTexto(evento.target.value)}
              />
            </label>
            <button type="submit">{equipeExiste ? "Atualizar equipe" : "Cadastrar equipe"}</button>
          </form>
        </>
      )}
    </div>
  );
}
