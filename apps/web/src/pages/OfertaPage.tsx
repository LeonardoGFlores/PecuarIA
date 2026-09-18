import { type FormEvent, useEffect, useState } from "react";
import {
  criarFornecedor,
  criarLogistica,
  criarOferta,
  listarFornecedores,
  listarLogistica,
  listarOfertas,
  removerFornecedor,
  removerLogistica,
  removerOferta,
} from "../api/client";
import type {
  Fornecedor,
  FornecedorInput,
  LogisticaOferta,
  LogisticaOfertaInput,
  OfertaRegional,
  OfertaRegionalInput,
  TipoFornecedor,
} from "../api/types";

const FORNECEDOR_VAZIO: FornecedorInput = {
  nome: "",
  tipo: "insumos",
  regiao: null,
  contato: null,
  fonte: "declarado_produtor",
};

function ofertaVazia(fornecedorId: string): OfertaRegionalInput {
  return {
    fornecedor_id: fornecedorId,
    categoria: "",
    especificacao: null,
    unidade: "",
    quantidade_disponivel: null,
    quantidade_minima: null,
    preco: null,
    condicoes: null,
    sazonalidade: null,
    data_registro: new Date().toISOString().slice(0, 10),
    validade_cotacao: null,
    fonte: "cotacao_fornecedor",
  };
}

const LOGISTICA_VAZIA: LogisticaOfertaInput = {
  distancia_km: null,
  prazo_entrega_dias: null,
  custo_frete: null,
};

function formatarData(data: string | null): string {
  if (!data) return "—";
  return new Date(data).toLocaleDateString("pt-BR");
}

export function OfertaPage() {
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [carregandoFornecedores, setCarregandoFornecedores] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [formFornecedor, setFormFornecedor] = useState<FornecedorInput>(FORNECEDOR_VAZIO);

  const [fornecedorSelecionadoId, setFornecedorSelecionadoId] = useState<string | null>(null);
  const [ofertas, setOfertas] = useState<OfertaRegional[]>([]);
  const [formOferta, setFormOferta] = useState<OfertaRegionalInput | null>(null);

  const [ofertaSelecionadaId, setOfertaSelecionadaId] = useState<string | null>(null);
  const [logisticas, setLogisticas] = useState<LogisticaOferta[]>([]);
  const [formLogistica, setFormLogistica] = useState<LogisticaOfertaInput>(LOGISTICA_VAZIA);

  async function recarregarFornecedores() {
    setCarregandoFornecedores(true);
    try {
      setFornecedores(await listarFornecedores());
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar fornecedores");
    } finally {
      setCarregandoFornecedores(false);
    }
  }

  useEffect(() => {
    recarregarFornecedores();
  }, []);

  useEffect(() => {
    if (!fornecedorSelecionadoId) {
      setOfertas([]);
      return;
    }
    setFormOferta(ofertaVazia(fornecedorSelecionadoId));
    listarOfertas(fornecedorSelecionadoId)
      .then(setOfertas)
      .catch((e) => setErro(e instanceof Error ? e.message : "Erro ao carregar ofertas"));
  }, [fornecedorSelecionadoId]);

  useEffect(() => {
    if (!ofertaSelecionadaId) {
      setLogisticas([]);
      return;
    }
    listarLogistica(ofertaSelecionadaId)
      .then(setLogisticas)
      .catch((e) => setErro(e instanceof Error ? e.message : "Erro ao carregar logística"));
  }, [ofertaSelecionadaId]);

  async function salvarFornecedor(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    try {
      await criarFornecedor(formFornecedor);
      setFormFornecedor(FORNECEDOR_VAZIO);
      await recarregarFornecedores();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao criar fornecedor");
    }
  }

  async function excluirFornecedor(fornecedorId: string) {
    setErro(null);
    try {
      await removerFornecedor(fornecedorId);
      if (fornecedorSelecionadoId === fornecedorId) setFornecedorSelecionadoId(null);
      await recarregarFornecedores();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao remover fornecedor");
    }
  }

  async function salvarOferta(evento: FormEvent) {
    evento.preventDefault();
    if (!formOferta || !fornecedorSelecionadoId) return;
    setErro(null);
    try {
      const payload: OfertaRegionalInput = {
        ...formOferta,
        data_registro: new Date(formOferta.data_registro).toISOString(),
        validade_cotacao: formOferta.validade_cotacao ? new Date(formOferta.validade_cotacao).toISOString() : null,
      };
      const criada = await criarOferta(payload);
      setOfertas([...ofertas, criada]);
      setFormOferta(ofertaVazia(fornecedorSelecionadoId));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao criar oferta");
    }
  }

  async function excluirOferta(ofertaId: string) {
    setErro(null);
    try {
      await removerOferta(ofertaId);
      setOfertas(ofertas.filter((o) => o.id !== ofertaId));
      if (ofertaSelecionadaId === ofertaId) setOfertaSelecionadaId(null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao remover oferta");
    }
  }

  async function salvarLogistica(evento: FormEvent) {
    evento.preventDefault();
    if (!ofertaSelecionadaId) return;
    setErro(null);
    try {
      const criada = await criarLogistica(ofertaSelecionadaId, formLogistica);
      setLogisticas([...logisticas, criada]);
      setFormLogistica(LOGISTICA_VAZIA);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao criar logística");
    }
  }

  async function excluirLogistica(logisticaId: string) {
    setErro(null);
    try {
      await removerLogistica(logisticaId);
      setLogisticas(logisticas.filter((l) => l.id !== logisticaId));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao remover logística");
    }
  }

  return (
    <div className="crud-page">
      <h1>Oferta regional</h1>
      <p>Animais, insumos, serviços e condições logísticas.</p>

      {erro && <div className="banner-erro">{erro}</div>}
      {!carregandoFornecedores && fornecedores.length === 0 && (
        <div className="banner-info">Nenhum fornecedor cadastrado ainda — cadastre o primeiro abaixo.</div>
      )}

      <h2>Fornecedores</h2>
      {fornecedores.length > 0 && (
        <table className="tabela-crud">
          <thead>
            <tr>
              <th>Nome</th>
              <th>Tipo</th>
              <th>Região</th>
              <th>Contato</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {fornecedores.map((fornecedor) => (
              <tr key={fornecedor.id} className={fornecedor.id === fornecedorSelecionadoId ? "linha-selecionada" : ""}>
                <td>{fornecedor.nome}</td>
                <td>{fornecedor.tipo}</td>
                <td>{fornecedor.regiao ?? "—"}</td>
                <td>{fornecedor.contato ?? "—"}</td>
                <td>
                  <button type="button" onClick={() => setFornecedorSelecionadoId(fornecedor.id)}>
                    Ver ofertas
                  </button>
                  <button type="button" onClick={() => excluirFornecedor(fornecedor.id)}>
                    Excluir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <form className="form-grid" onSubmit={salvarFornecedor}>
        <h3>Novo fornecedor</h3>
        <label>
          Nome
          <input
            required
            value={formFornecedor.nome}
            onChange={(evento) => setFormFornecedor({ ...formFornecedor, nome: evento.target.value })}
          />
        </label>
        <label>
          Tipo
          <select
            value={formFornecedor.tipo}
            onChange={(evento) => setFormFornecedor({ ...formFornecedor, tipo: evento.target.value as TipoFornecedor })}
          >
            <option value="animais">Animais</option>
            <option value="insumos">Insumos</option>
            <option value="servicos">Serviços</option>
            <option value="frete">Frete</option>
            <option value="comprador">Comprador</option>
          </select>
        </label>
        <label>
          Região
          <input
            value={formFornecedor.regiao ?? ""}
            onChange={(evento) => setFormFornecedor({ ...formFornecedor, regiao: evento.target.value || null })}
          />
        </label>
        <label>
          Contato
          <input
            value={formFornecedor.contato ?? ""}
            onChange={(evento) => setFormFornecedor({ ...formFornecedor, contato: evento.target.value || null })}
          />
        </label>
        <button type="submit">Cadastrar fornecedor</button>
      </form>

      {fornecedorSelecionadoId && formOferta && (
        <>
          <h2>Ofertas de {fornecedores.find((f) => f.id === fornecedorSelecionadoId)?.nome}</h2>
          {ofertas.length > 0 && (
            <table className="tabela-crud">
              <thead>
                <tr>
                  <th>Categoria</th>
                  <th>Unidade</th>
                  <th>Qtd. disponível</th>
                  <th>Preço</th>
                  <th>Validade da cotação</th>
                  <th></th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {ofertas.map((oferta) => (
                  <tr key={oferta.id} className={oferta.id === ofertaSelecionadaId ? "linha-selecionada" : ""}>
                    <td>{oferta.categoria}</td>
                    <td>{oferta.unidade}</td>
                    <td>{oferta.quantidade_disponivel ?? "—"}</td>
                    <td>{oferta.preco ?? "—"}</td>
                    <td>
                      {formatarData(oferta.validade_cotacao)}{" "}
                      {oferta.vencida && <span className="badge-vencida">vencida</span>}
                    </td>
                    <td>
                      <button type="button" onClick={() => setOfertaSelecionadaId(oferta.id)}>
                        Ver logística
                      </button>
                    </td>
                    <td>
                      <button type="button" onClick={() => excluirOferta(oferta.id)}>
                        Excluir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <form className="form-grid" onSubmit={salvarOferta}>
            <h3>Nova oferta</h3>
            <label>
              Categoria
              <input
                required
                value={formOferta.categoria}
                onChange={(evento) => setFormOferta({ ...formOferta, categoria: evento.target.value })}
              />
            </label>
            <label>
              Especificação
              <input
                value={formOferta.especificacao ?? ""}
                onChange={(evento) => setFormOferta({ ...formOferta, especificacao: evento.target.value || null })}
              />
            </label>
            <label>
              Unidade
              <input
                required
                value={formOferta.unidade}
                onChange={(evento) => setFormOferta({ ...formOferta, unidade: evento.target.value })}
              />
            </label>
            <label>
              Quantidade disponível
              <input
                type="number"
                min={0}
                step="0.01"
                value={formOferta.quantidade_disponivel ?? ""}
                onChange={(evento) =>
                  setFormOferta({
                    ...formOferta,
                    quantidade_disponivel: evento.target.value === "" ? null : Number(evento.target.value),
                  })
                }
              />
            </label>
            <label>
              Quantidade mínima
              <input
                type="number"
                min={0}
                step="0.01"
                value={formOferta.quantidade_minima ?? ""}
                onChange={(evento) =>
                  setFormOferta({
                    ...formOferta,
                    quantidade_minima: evento.target.value === "" ? null : Number(evento.target.value),
                  })
                }
              />
            </label>
            <label>
              Preço
              <input
                type="number"
                min={0}
                step="0.01"
                value={formOferta.preco ?? ""}
                onChange={(evento) =>
                  setFormOferta({ ...formOferta, preco: evento.target.value === "" ? null : Number(evento.target.value) })
                }
              />
            </label>
            <label>
              Condições
              <input
                value={formOferta.condicoes ?? ""}
                onChange={(evento) => setFormOferta({ ...formOferta, condicoes: evento.target.value || null })}
              />
            </label>
            <label>
              Sazonalidade
              <input
                value={formOferta.sazonalidade ?? ""}
                onChange={(evento) => setFormOferta({ ...formOferta, sazonalidade: evento.target.value || null })}
              />
            </label>
            <label>
              Data de registro
              <input
                type="date"
                required
                value={formOferta.data_registro.slice(0, 10)}
                onChange={(evento) => setFormOferta({ ...formOferta, data_registro: evento.target.value })}
              />
            </label>
            <label>
              Validade da cotação
              <input
                type="date"
                value={formOferta.validade_cotacao?.slice(0, 10) ?? ""}
                onChange={(evento) => setFormOferta({ ...formOferta, validade_cotacao: evento.target.value || null })}
              />
            </label>
            <label>
              Fonte
              <input
                required
                value={formOferta.fonte}
                onChange={(evento) => setFormOferta({ ...formOferta, fonte: evento.target.value })}
              />
            </label>
            <button type="submit">Cadastrar oferta</button>
          </form>
        </>
      )}

      {ofertaSelecionadaId && (
        <>
          <h2>Logística</h2>
          {logisticas.length > 0 && (
            <table className="tabela-crud">
              <thead>
                <tr>
                  <th>Distância (km)</th>
                  <th>Prazo de entrega (dias)</th>
                  <th>Custo do frete</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {logisticas.map((logistica) => (
                  <tr key={logistica.id}>
                    <td>{logistica.distancia_km ?? "—"}</td>
                    <td>{logistica.prazo_entrega_dias ?? "—"}</td>
                    <td>{logistica.custo_frete ?? "—"}</td>
                    <td>
                      <button type="button" onClick={() => excluirLogistica(logistica.id)}>
                        Excluir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <form className="form-grid" onSubmit={salvarLogistica}>
            <h3>Nova opção de logística</h3>
            <label>
              Distância (km)
              <input
                type="number"
                min={0}
                step="0.01"
                value={formLogistica.distancia_km ?? ""}
                onChange={(evento) =>
                  setFormLogistica({
                    ...formLogistica,
                    distancia_km: evento.target.value === "" ? null : Number(evento.target.value),
                  })
                }
              />
            </label>
            <label>
              Prazo de entrega (dias)
              <input
                type="number"
                min={0}
                value={formLogistica.prazo_entrega_dias ?? ""}
                onChange={(evento) =>
                  setFormLogistica({
                    ...formLogistica,
                    prazo_entrega_dias: evento.target.value === "" ? null : Number(evento.target.value),
                  })
                }
              />
            </label>
            <label>
              Custo do frete
              <input
                type="number"
                min={0}
                step="0.01"
                value={formLogistica.custo_frete ?? ""}
                onChange={(evento) =>
                  setFormLogistica({
                    ...formLogistica,
                    custo_frete: evento.target.value === "" ? null : Number(evento.target.value),
                  })
                }
              />
            </label>
            <button type="submit">Cadastrar logística</button>
          </form>
        </>
      )}
    </div>
  );
}
