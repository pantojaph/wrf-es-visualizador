"""Visualizador Streamlit dos experimentos de precipitação WRF-ES."""
from pathlib import Path
import json
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from shapely.geometry import Point, shape
from shapely import intersects_xy
import streamlit as st


st.set_page_config(page_title="WRF-ES | Precipitação", page_icon="🌧️", layout="wide")
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "dados"
LEVELS = [1, 5, 10, 20, 30, 50, 75, 100, 150, 200, 300, 400, 500]
# Mesmas 12 cores das classes >=1 mm dos mapas operacionais V3.
CMAP = ListedColormap(plt.get_cmap("turbo", 13).colors[1:], name="wrf_es_prp")
CMAP.set_bad("white")
CMAP.set_under("white")
CMAP.set_over("#590000")
NORM = BoundaryNorm(LEVELS, CMAP.N)
ES_EXTENT = (-42.3, -39.3, -21.5, -17.5)  # oeste, leste, sul, norte
PATTERN = re.compile(r"wrf_(gfs|ecmwf)_(\d{8})_(\d{2})_(d0\d)_precipitacao\.npz")


def catalogo():
    items = []
    for path in sorted(DATA_DIR.glob("*.npz")):
        match = PATTERN.fullmatch(path.name)
        if match:
            forcing, date, hour, domain = match.groups()
            label = f"{date[6:8]}/{date[4:6]}/{date[:4]} {hour}Z | {forcing.upper()} | {domain.upper()}"
        elif path.name == "wrf_d02_precipitacao.npz":
            label = "Março de 2024 | histórico | d02 (3 km)"
        else:
            continue
        items.append((label, path))
    return items


@st.cache_data(show_spinner="Carregando grade meteorológica…")
def carregar(caminho, mtime):
    with np.load(caminho) as z:
        lat = z["lat"].astype(np.float32)
        lon = z["lon"].astype(np.float32)
        tempos = z["tempos"].astype("datetime64[s]")
        prp = z["chuva_horaria"].astype(np.float32)
    if lat.shape != lon.shape or prp.ndim != 3 or prp.shape[1:] != lat.shape:
        raise ValueError("Dimensões inconsistentes no NPZ.")
    if len(tempos) != len(prp) + 1 or not np.all(np.diff(tempos) == np.timedelta64(1, "h")):
        raise ValueError("A série temporal não contém intervalos horários consecutivos.")
    if not np.isfinite(prp).all() or np.min(prp) < -0.001:
        raise ValueError("Precipitação com valores ausentes ou incrementos negativos.")
    return lat, lon, tempos, np.maximum(prp, 0)


@st.cache_resource(show_spinner=False)
def cartografia():
    boundary = DATA_DIR / "es_continental.geojson"
    municipal = DATA_DIR / "municipios_es_continental.geojson"
    if not boundary.is_file() or not municipal.is_file():
        return None, []
    with boundary.open(encoding="utf-8") as f:
        estado = shape(json.load(f)["features"][0]["geometry"])
    with municipal.open(encoding="utf-8") as f:
        features = json.load(f)["features"]
    municipios = [
        (str(feat.get("properties", {}).get("NM_MUN", "Município")), shape(feat["geometry"]))
        for feat in features
    ]
    if estado.is_empty or not municipios:
        raise ValueError("Cartografia continental vazia.")
    return estado, municipios


def plot_geometry(ax, geom, **kwargs):
    if geom.geom_type in ("Polygon", "LineString", "LinearRing"):
        line = geom.exterior if geom.geom_type == "Polygon" else geom
        coords = np.asarray(line.coords)
        ax.plot(coords[:, 0], coords[:, 1], **kwargs)
    elif hasattr(geom, "geoms"):
        for sub in geom.geoms:
            plot_geometry(ax, sub, **kwargs)


def maximo(campo, lat, lon, mask=None):
    valid = np.isfinite(campo)
    if mask is not None:
        valid &= mask
    if not valid.any():
        return None
    values = np.where(valid, campo, -np.inf)
    iy, ix = np.unravel_index(np.argmax(values), values.shape)
    return float(campo[iy, ix]), float(lat[iy, ix]), float(lon[iy, ix])


def gerar_mapa(campo, lat, lon, estado, municipios, region, ponto, max_es, period):
    fig, ax = plt.subplots(figsize=(8, 8), layout="constrained")
    vals = np.ma.masked_where(~np.isfinite(campo) | (campo < 1.0), campo)
    art = ax.contourf(
        lon, lat, vals, levels=LEVELS,
        cmap=CMAP, norm=NORM, extend="max", corner_mask=True, antialiased=False
    )
    if region == "Espírito Santo e entorno":
        west, east, south, north = ES_EXTENT
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)
    else:
        ax.set_xlim(float(np.nanmin(lon)), float(np.nanmax(lon)))
        ax.set_ylim(float(np.nanmin(lat)), float(np.nanmax(lat)))
    if estado is not None:
        for _, geom in municipios:
            plot_geometry(ax, geom.boundary, color="#666666", linewidth=0.28, zorder=5)
        plot_geometry(ax, estado.boundary, color="black", linewidth=1.4, zorder=7)
    if max_es is not None:
        ax.plot(max_es[2], max_es[1], marker="*", markersize=11,
                markerfacecolor="black", markeredgecolor="white", zorder=9)
    ax.plot(float(ponto[1]), float(ponto[0]), "o", markersize=5,
            markerfacecolor="white", markeredgecolor="black", zorder=10)
    central_lat = (ax.get_ylim()[0] + ax.get_ylim()[1]) / 2
    ax.set_aspect(1.0 / np.cos(np.deg2rad(central_lat)), adjustable="box")
    ax.grid(True, linestyle="--", linewidth=0.35, alpha=0.4)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(period, fontsize=11, pad=10)
    cb = fig.colorbar(art, ax=ax, orientation="horizontal", fraction=0.046,
                      pad=0.075, ticks=LEVELS)
    cb.set_label("Precipitação acumulada (mm) | < 1 mm em branco")
    cb.ax.tick_params(labelsize=8)
    return fig


st.title("WRF-ES | Precipitação")
st.caption("WRF-ARW 4.8.0 · Campos simulados · Sem suavização numérica · Horários em UTC e BRT")
files = catalogo()
if not files:
    st.warning("Nenhuma base NPZ encontrada em dados/. Consulte o README para exportar as rodadas.")
    st.stop()

estado, municipios = cartografia()
with st.sidebar:
    st.header("Experimento")
    index = len(files) - 1
    item = st.selectbox("Rodada e domínio", options=range(len(files)),
                        index=index, format_func=lambda n: files[n][0])
    label, arquivo = files[item]
    lat, lon, tempos, chuva = carregar(str(arquivo), arquivo.stat().st_mtime_ns)
    n = len(chuva)
    opcoes = [h for h in [1, 3, 6, 12, 24, 48, 72, 90] if h <= n]
    janela = st.selectbox("Acumulado", opcoes, index=min(4, len(opcoes) - 1),
                          format_func=lambda h: f"{h} horas")
    fim = st.slider("Prazo final de previsão (+h)", min_value=janela, max_value=n, value=n)
    periodo = pd.Timestamp(tempos[fim], tz="UTC")
    st.caption(f"Validade: {periodo:%d/%m/%Y %H:%M} UTC | "
               f"{periodo.tz_convert('America/Sao_Paulo'):%d/%m/%Y %H:%M} BRT")
    if estado is None:
        st.info("Sem cartografia local: recorte e máximo estadual desabilitados. Exporte os GeoJSON com o script fornecido.")
        region = "Domínio completo"
    else:
        region = st.radio("Enquadramento", ["Espírito Santo e entorno", "Domínio completo"])
    st.divider()
    st.subheader("Consulta por coordenadas")
    consulta_lat = st.number_input("Latitude", value=-21.064, format="%.4f")
    consulta_lon = st.number_input("Longitude", value=-41.366, format="%.4f")

# Incrementos cobrem (tempos[k], tempos[k+1]], com índice final fim.
campo = np.sum(chuva[fim - janela:fim], axis=0, dtype=np.float64).astype(np.float32)
phi = np.deg2rad(consulta_lat)
a = (np.sin((np.deg2rad(lat) - phi) / 2) ** 2
     + np.cos(phi) * np.cos(np.deg2rad(lat))
     * np.sin(np.deg2rad(lon - consulta_lon) / 2) ** 2)
dist = 2 * 6371 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
j, i = np.unravel_index(np.argmin(dist), dist.shape)
ponto = (float(lat[j, i]), float(lon[j, i]))
mask = intersects_xy(estado, lon, lat) if estado is not None else None
max_es = maximo(campo, lat, lon, mask) if mask is not None else None
max_full = maximo(campo, lat, lon)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Máximo no domínio", f"{max_full[0]:.1f} mm")
col2.metric("Máximo no ES continental", f"{max_es[0]:.1f} mm" if max_es else "Indisponível")
col3.metric("Ponto consultado", f"{campo[j, i]:.1f} mm")
col4.metric("Distância à grade", f"{dist[j, i]:.2f} km")

inicio_utc = pd.Timestamp(tempos[fim - janela], tz="UTC")
fim_utc = pd.Timestamp(tempos[fim], tz="UTC")
period = (f"{label} | {janela} h\n"
          f"UTC: {inicio_utc:%d/%m %HZ}–{fim_utc:%d/%m %HZ} | "
          f"BRT: {inicio_utc.tz_convert('America/Sao_Paulo'):%d/%m %Hh}–"
          f"{fim_utc.tz_convert('America/Sao_Paulo'):%d/%m %Hh}")

esq, dir = st.columns([1.35, 1])
with esq:
    st.subheader("Distribuição espacial da precipitação")
    fig = gerar_mapa(campo, lat, lon, estado, municipios, region, ponto, max_es, period)
    st.pyplot(fig, width="stretch")
    plt.close(fig)
    st.caption("Contornos interpolados apenas para representação visual. "
               "Cálculos e séries utilizam a grade nativa, sem filtro ou interpolação.")
    if max_es:
        municipio = next((name for name, geom in municipios
                          if geom.covers(Point(max_es[2], max_es[1]))),
                         "Município não identificado")
        st.write(f"**Máximo no ES:** {max_es[0]:.1f} mm | "
                 f"{municipio} | {max_es[1]:.4f}°, {max_es[2]:.4f}°")

with dir:
    st.subheader("Série horária no ponto consultado")
    instantes = pd.to_datetime(tempos[1:], utc=True)
    serie = pd.DataFrame({
        "Horário UTC": instantes,
        "Horário BRT": instantes.tz_convert("America/Sao_Paulo"),
        "Precipitação (mm)": chuva[:, j, i]
    })
    bars = go.Figure(go.Bar(x=serie["Horário BRT"], y=serie["Precipitação (mm)"],
                            marker_color="#2563eb"))
    bars.update_layout(
        height=350, xaxis_title="Fim do intervalo (BRT)",
        yaxis_title="Precipitação horária (mm)",
        margin=dict(l=25, r=10, t=15, b=35)
    )
    st.plotly_chart(bars, width="stretch")
    st.write(f"**Ponto WRF:** {ponto[0]:.4f}°, {ponto[1]:.4f}° | grade j={j}, i={i}")
    st.download_button("Baixar série horária CSV",
                       data=serie.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"wrf_{arquivo.stem}_serie_horaria.csv",
                       mime="text/csv")
    st.caption("A seleção de coordenadas retorna o centro da célula mais próxima.")
st.info("Previsões experimentais: não representam observações ou validação do modelo.")
