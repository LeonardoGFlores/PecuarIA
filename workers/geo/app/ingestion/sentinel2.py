"""Tasks Celery do pipeline NDVI/EVI (docs/specs/02): descoberta diaria de
cenas Sentinel-2 L2A por fazenda, filtro de nuvem via metadado STAC (sem
tocar raster), e processamento de indices por par (cena, area_produtiva).

Ver docstring de `app.clients.stac` para as ressalvas sobre nomes de asset
e formato de metadados nao confirmados contra a API real.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import uuid

import httpx
import rasterio.errors
from shapely.geometry import shape
from sqlalchemy import select, text, update

from app import db_enums
from app.clients import stac as stac_client
from app.clients import storage
from app.config import get_settings
from app.db import get_engine, get_table
from app.ingestion.manifesto import IngestaoParcialError, rastrear_execucao
from app.ingestion.upsert import upsert_cena_satelite, upsert_indice_vegetacao
from app.processing import escala, estatisticas, geometria, indices, raster_io
from app.tasks import celery_app
from app.versioning import VERSAO_DESCOBERTA_SENTINEL2, VERSAO_PROCESSAMENTO_NDVI_EVI

logger = logging.getLogger(__name__)

OVERLAP_DESCOBERTA_DIAS = 3
BANDAS_ESPECTRAIS = ("red", "nir", "blue")


class FazendaNaoEncontradaError(RuntimeError):
    """A fazenda referenciada por uma task de descoberta nao existe mais."""


class AreaNaoEncontradaError(RuntimeError):
    """A area produtiva referenciada por uma task de processamento nao existe mais."""


class CenaNaoEncontradaError(RuntimeError):
    """A cena referenciada por uma task de processamento nao existe mais."""


def _geometria_geojson(conn, tabela: str, coluna_id: str, valor_id: uuid.UUID) -> dict | None:
    linha = conn.execute(
        text(f"SELECT ST_AsGeoJSON(geom) AS geojson FROM {tabela} WHERE {coluna_id} = :id"),
        {"id": str(valor_id)},
    ).first()
    return json.loads(linha.geojson) if linha is not None else None


def _janela_de_busca(conn, fazenda_id: uuid.UUID, dias_backfill: int) -> tuple[dt.date, dt.date]:
    """Alta-marca por fazenda sem tabela nova: MAX(data_aquisicao) de
    cena_satelite cujo geom intersecta a fazenda. `NULL` -> backfill
    (revisit ~5 dias, cobre a serie inicial sem repetir o backfill de anos
    usado no clima); senao -> busca de `max_date - OVERLAP_DESCOBERTA_DIAS`
    ate hoje."""
    linha = conn.execute(
        text(
            """
            SELECT MAX(c.data_aquisicao) AS ultima_data
            FROM cena_satelite c, fazenda f
            WHERE f.id = :fazenda_id AND ST_Intersects(c.geom, f.geom)
            """
        ),
        {"fazenda_id": str(fazenda_id)},
    ).first()

    hoje = dt.date.today()
    if linha is None or linha.ultima_data is None:
        inicio = hoje - dt.timedelta(days=dias_backfill)
    else:
        inicio = linha.ultima_data.date() - dt.timedelta(days=OVERLAP_DESCOBERTA_DIAS)
    return inicio, hoje


def _extrair_tile_id(item: stac_client.ItemSTAC) -> str:
    """Prefere a extensao MGRS do STAC (`s2:mgrs_tile`/`grid:code`); sem
    confirmacao ao vivo de qual delas o Earth Search expoe, cai para o
    segundo segmento do id do item (formato tipico `S2A_<tile>_<data>_...`)."""
    tile_id = item.propriedades.get("s2:mgrs_tile") or item.propriedades.get("grid:code")
    if tile_id:
        return str(tile_id)
    partes = item.id.split("_")
    return partes[1] if len(partes) > 1 else item.id


def _resolver_ativos(item: stac_client.ItemSTAC) -> dict:
    """Resolve escala/offset por asset uma unica vez, na descoberta —
    evita reconsultar o STAC a cada area processada da mesma cena
    (cacheado em `cena_satelite.ativos`)."""
    ativos: dict[str, dict] = {}
    for nome, asset in item.ativos.items():
        scale, offset = escala.resolver_escala_offset(asset, item.propriedades)
        ativos[nome] = {"href": asset["href"], "scale": scale, "offset": offset}
    return ativos


@celery_app.task(name="satelite.despachar_descoberta")
def despachar_descoberta() -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        fazenda_tbl = get_table("fazenda")
        fazendas = conn.execute(select(fazenda_tbl.c.id)).fetchall()

    for fazenda in fazendas:
        descobrir_cenas.delay(str(fazenda.id))
    return {"despachadas": len(fazendas)}


@celery_app.task(name="satelite.descobrir_cenas", queue="satelite_descoberta")
def descobrir_cenas(fazenda_id: str) -> dict:
    settings = get_settings()
    engine = get_engine()
    fazenda_uuid = uuid.UUID(fazenda_id)

    with engine.connect() as conn:
        geometria_fazenda = _geometria_geojson(conn, "fazenda", "id", fazenda_uuid)
        if geometria_fazenda is None:
            raise FazendaNaoEncontradaError(f"fazenda {fazenda_id} nao encontrada")
        inicio, fim = _janela_de_busca(conn, fazenda_uuid, settings.sentinel2_backfill_dias)

        with rastrear_execucao(
            conn,
            tipo=db_enums.TIPO_EXECUCAO_INGESTAO_SATELITE,
            entrada_fontes=[f"SENTINEL2_L2A:fazenda={fazenda_id}"],
            parametros={
                "janela_inicio": inicio.isoformat(),
                "janela_fim": fim.isoformat(),
                "limiar_nuvem_cena_pct": settings.sentinel2_limiar_nuvem_cena_pct,
            },
            versao_pipeline=VERSAO_DESCOBERTA_SENTINEL2,
        ) as (_execucao_id, resultado):
            try:
                itens = stac_client.buscar_cenas(
                    geometria_fazenda,
                    inicio,
                    fim,
                    cobertura_nuvem_maxima_pct=settings.sentinel2_limiar_nuvem_cena_pct,
                )
            except httpx.HTTPError as exc:
                raise IngestaoParcialError(
                    f"falha ao buscar STAC para fazenda {fazenda_id}: {exc}"
                ) from exc

            indice_tbl = get_table("indice_vegetacao_area")
            cenas_novas = 0
            areas_despachadas = 0

            for item in itens:
                rejeitada = item.cobertura_nuvem_pct > settings.sentinel2_limiar_nuvem_cena_pct
                cena_id, foi_criada = upsert_cena_satelite(
                    conn,
                    {
                        "fonte": db_enums.FONTE_CENA_SENTINEL2_L2A,
                        "item_stac_id": item.id,
                        "tile_id": _extrair_tile_id(item),
                        "data_aquisicao": dt.datetime.fromisoformat(item.data_aquisicao.replace("Z", "+00:00")),
                        "cobertura_nuvem_cena_pct": item.cobertura_nuvem_pct,
                        "geom": f"SRID=4326;{shape(item.geometria).wkt}",
                        "status_processamento": (
                            db_enums.STATUS_CENA_REJEITADA if rejeitada else db_enums.STATUS_CENA_PENDENTE
                        ),
                        "ativos": _resolver_ativos(item),
                    },
                )
                if foi_criada:
                    cenas_novas += 1
                resultado["saida_referencias"].append(
                    f"cena_satelite:item_stac_id={item.id}:criada={foi_criada}:rejeitada={rejeitada}"
                )

                if rejeitada:
                    continue

                areas = conn.execute(
                    text(
                        """
                        SELECT a.id AS area_id
                        FROM area_produtiva a, cena_satelite c
                        WHERE a.fazenda_id = :fazenda_id AND c.id = :cena_id
                          AND ST_Intersects(a.geom, c.geom)
                        """
                    ),
                    {"fazenda_id": str(fazenda_uuid), "cena_id": str(cena_id)},
                ).fetchall()

                for area in areas:
                    ja_processada = conn.execute(
                        select(indice_tbl.c.id).where(
                            indice_tbl.c.area_produtiva_id == area.area_id,
                            indice_tbl.c.cena_id == cena_id,
                        )
                    ).first()
                    if ja_processada is not None:
                        continue
                    processar_cena_area.delay(str(cena_id), str(area.area_id))
                    areas_despachadas += 1

            conn.commit()

    return {"itens_encontrados": len(itens), "cenas_novas": cenas_novas, "areas_despachadas": areas_despachadas}


def _reconciliar_redundancia_do_dia(
    conn,
    area_produtiva_id: uuid.UUID,
    data_aquisicao: dt.datetime,
    cena_id_atual: uuid.UUID,
    geometria_area_geojson: dict,
    cobertura_atual_pct: float,
) -> None:
    """Duas cenas no mesmo dia cobrindo "a mesma parte" da area: a de menor
    cobertura valida vira REDUNDANTE em `cena_satelite` — sua linha em
    `indice_vegetacao_area` continua existindo como evidencia, so deixa de
    ser a leitura "principal" do dia (nunca apagada). Barata, no-op se so
    ha uma cena no dia para esta area."""
    cena_tbl = get_table("cena_satelite")
    candidatas = conn.execute(
        text(
            """
            SELECT DISTINCT c.id AS cena_id, ST_AsGeoJSON(c.geom) AS geojson, iva.cobertura_valida_pct AS cobertura_pct
            FROM indice_vegetacao_area iva
            JOIN cena_satelite c ON c.id = iva.cena_id
            WHERE iva.area_produtiva_id = :area_id
              AND iva.tipo = :tipo_referencia
              AND DATE(iva.data_aquisicao) = :data
              AND c.status_processamento != :status_redundante
            """
        ),
        {
            "area_id": str(area_produtiva_id),
            "tipo_referencia": db_enums.TIPO_INDICE_NDVI,
            "data": data_aquisicao.date().isoformat(),
            "status_redundante": db_enums.STATUS_CENA_REDUNDANTE,
        },
    ).fetchall()

    if len(candidatas) < 2:
        return

    geometria_area = shape(geometria_area_geojson)
    footprint_atual = next((c for c in candidatas if str(c.cena_id) == str(cena_id_atual)), None)
    if footprint_atual is None:
        return

    for outra in candidatas:
        if str(outra.cena_id) == str(cena_id_atual):
            continue
        mesma_parte = geometria.classificar_sobreposicao(
            geometria_area,
            shape(json.loads(footprint_atual.geojson)),
            shape(json.loads(outra.geojson)),
        )
        if not mesma_parte:
            continue
        perdedora_id = (
            cena_id_atual if float(cobertura_atual_pct) < float(outra.cobertura_pct) else outra.cena_id
        )
        conn.execute(
            update(cena_tbl)
            .where(cena_tbl.c.id == perdedora_id)
            .values(status_processamento=db_enums.STATUS_CENA_REDUNDANTE)
        )
    conn.commit()


@celery_app.task(
    name="satelite.processar_cena_area",
    queue="satelite_processamento",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def processar_cena_area(self, cena_id: str, area_produtiva_id: str) -> dict:
    engine = get_engine()
    cena_uuid = uuid.UUID(cena_id)
    area_uuid = uuid.UUID(area_produtiva_id)

    cena_tbl = get_table("cena_satelite")
    area_tbl = get_table("area_produtiva")

    with engine.connect() as conn:
        cena = conn.execute(select(cena_tbl).where(cena_tbl.c.id == cena_uuid)).first()
        if cena is None:
            raise CenaNaoEncontradaError(f"cena_satelite {cena_id} nao encontrada")

        area = conn.execute(select(area_tbl.c.fazenda_id).where(area_tbl.c.id == area_uuid)).first()
        geometria_area = _geometria_geojson(conn, "area_produtiva", "id", area_uuid)
        if area is None or geometria_area is None:
            raise AreaNaoEncontradaError(f"area_produtiva {area_produtiva_id} nao encontrada")

    hrefs = {nome: ativo["href"] for nome, ativo in cena.ativos.items()}
    escalas_offsets = {
        nome: (ativo["scale"], ativo["offset"]) for nome, ativo in cena.ativos.items() if nome in BANDAS_ESPECTRAIS
    }

    try:
        recorte = raster_io.recortar_cena_para_area(hrefs, escalas_offsets, geometria_area)
    except rasterio.errors.RasterioIOError as exc:
        raise self.retry(exc=exc)

    settings = get_settings()
    ndvi = indices.calcular_ndvi(recorte.red, recorte.nir)
    evi = indices.calcular_evi(recorte.red, recorte.nir, recorte.blue)
    limiar_cobertura = settings.sentinel2_limiar_cobertura_valida_minima_pct

    stats_ndvi = estatisticas.calcular_estatisticas(ndvi, recorte.pixels_area_intersecao_cena, limiar_cobertura)
    stats_evi = estatisticas.calcular_estatisticas(evi, recorte.pixels_area_intersecao_cena, limiar_cobertura)

    with engine.connect() as conn:
        with rastrear_execucao(
            conn,
            tipo=db_enums.TIPO_EXECUCAO_INDICE_VEGETACAO,
            entrada_fontes=[f"cena_satelite:{cena_id}"],
            parametros={
                "area_produtiva_id": area_produtiva_id,
                "cena_id": cena_id,
                "limiar_cobertura_valida_minima_pct": limiar_cobertura,
            },
            versao_pipeline=VERSAO_PROCESSAMENTO_NDVI_EVI,
        ) as (_execucao_id, resultado):
            storage_client = storage.novo_client_s3()
            storage.garantir_bucket(storage_client, settings.storage_bucket)

            data_str = cena.data_aquisicao.strftime("%Y-%m-%d")
            linhas = []
            for tipo, indice_array, stats in (
                (db_enums.TIPO_INDICE_NDVI, ndvi, stats_ndvi),
                (db_enums.TIPO_INDICE_EVI, evi, stats_evi),
            ):
                chave = (
                    f"ndvi-evi/{area.fazenda_id}/{area_produtiva_id}/{data_str}/{cena_id}/"
                    f"{VERSAO_PROCESSAMENTO_NDVI_EVI}/{tipo}.tif"
                )
                conteudo = raster_io.gerar_geotiff_banda_unica_bytes(indice_array, recorte.transform, recorte.crs)
                storage.salvar_objeto(
                    storage_client, settings.storage_bucket, chave, conteudo, content_type="image/tiff"
                )

                linhas.append(
                    {
                        "area_produtiva_id": area_uuid,
                        "cena_id": cena_uuid,
                        "tipo": tipo,
                        "data_aquisicao": cena.data_aquisicao,
                        "cobertura_valida_pct": stats.cobertura_valida_pct,
                        "mediana": stats.mediana,
                        "p10": stats.p10,
                        "p25": stats.p25,
                        "p75": stats.p75,
                        "p90": stats.p90,
                        "desvio_padrao": stats.desvio_padrao,
                        "qualidade": (
                            db_enums.QUALIDADE_INDICE_SUFICIENTE
                            if stats.qualidade_suficiente
                            else db_enums.QUALIDADE_INDICE_INSUFICIENTE
                        ),
                        "versao_processamento": VERSAO_PROCESSAMENTO_NDVI_EVI,
                        "raster_ref": chave,
                    }
                )
                resultado["saida_referencias"].append(
                    f"indice_vegetacao_area:area={area_produtiva_id}:cena={cena_id}:tipo={tipo}"
                )

            upsert_indice_vegetacao(conn, linhas)
            # `status_processamento=PROCESSADA` marca que a cena passou pelo
            # pipeline ao menos uma vez — usado pela rede de seguranca
            # (despachar_processamento_pendente) para nao redespachar
            # eternamente; a integridade por area continua garantida pela
            # propria linha em indice_vegetacao_area, checada na descoberta.
            conn.execute(
                update(cena_tbl)
                .where(cena_tbl.c.id == cena_uuid)
                .values(status_processamento=db_enums.STATUS_CENA_PROCESSADA)
            )
            conn.commit()

            _reconciliar_redundancia_do_dia(
                conn, area_uuid, cena.data_aquisicao, cena_uuid, geometria_area, stats_ndvi.cobertura_valida_pct
            )

    return {
        "status": "processada",
        "cobertura_ndvi_pct": stats_ndvi.cobertura_valida_pct,
        "cobertura_evi_pct": stats_evi.cobertura_valida_pct,
    }


@celery_app.task(name="satelite.despachar_processamento_pendente", queue="satelite_processamento")
def despachar_processamento_pendente() -> dict:
    """Rede de seguranca: redespacha pares (cena PENDENTE, area que a
    intersecta) sem `indice_vegetacao_area` correspondente ainda — cobre
    mensagem perdida ou worker reiniciado no meio do processamento (mesmo
    espirito de `despachar_refresh` da Fase 2)."""
    engine = get_engine()
    with engine.connect() as conn:
        pendentes = conn.execute(
            text(
                """
                SELECT DISTINCT c.id AS cena_id, a.id AS area_id
                FROM cena_satelite c
                JOIN area_produtiva a ON ST_Intersects(a.geom, c.geom)
                LEFT JOIN indice_vegetacao_area iva
                    ON iva.cena_id = c.id AND iva.area_produtiva_id = a.id
                WHERE c.status_processamento = :status_pendente
                  AND iva.id IS NULL
                """
            ),
            {"status_pendente": db_enums.STATUS_CENA_PENDENTE},
        ).fetchall()

    for linha in pendentes:
        processar_cena_area.delay(str(linha.cena_id), str(linha.area_id))
    return {"redespachadas": len(pendentes)}
