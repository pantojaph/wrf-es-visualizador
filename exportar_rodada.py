"""Exporta os NetCDFs simplificados WRF-ES para o visualizador Streamlit.

Uso:
python exportar_rodada.py --input /.../POST/NETCDF --saida dados
"""
import argparse
from pathlib import Path
import re

import numpy as np
import xarray as xr


def exportar(arquivo, saida, tolerancia=0.001):
    nome = arquivo.name
    match = re.fullmatch(
        r"wrf_es_(gfs|ecmwf)_(\d{8})_(\d{2})_precip_(d0\d)\.nc", nome
    )
    if not match:
        raise ValueError(f"Nome fora do padrão: {nome}")
    modelo, data, hora, dominio = match.groups()

    with xr.open_dataset(arquivo, engine="netcdf4") as ds:
        lat = ds["lat"].values.astype(np.float32)
        lon = ds["lon"].values.astype(np.float32)
        acum = ds["prp_accum"].values.astype(np.float32)
        tempo = ds["time"].values.astype("datetime64[s]")
        horas = ds["prp_hourly"].values.astype(np.float32)

    if acum.ndim != 3 or lat.shape != lon.shape or acum.shape[1:] != lat.shape:
        raise ValueError(f"Dimensões inconsistentes: {arquivo}")
    if len(tempo) != len(acum) or len(tempo) < 2:
        raise ValueError("Eixo temporal incorreto.")
    if np.any(np.diff(tempo) != np.timedelta64(1, "h")):
        raise ValueError("Os horários não têm resolução contínua de uma hora.")
    if not np.isfinite(acum).all() or not np.isfinite(horas[1:]).all():
        raise ValueError("Valores inválidos nos campos de precipitação.")

    incrementos = np.diff(acum.astype(np.float64), axis=0)
    minimo = float(np.min(incrementos))
    if minimo < -tolerancia:
        raise ValueError(f"Incrementos negativos significativos: {minimo:.6f} mm")
    if np.max(np.abs(np.maximum(incrementos, 0.0) - horas[1:])) > 0.02:
        raise ValueError("Precipitação horária não confere com diferença dos acumulados.")
    incrementos = np.maximum(incrementos, 0.0).astype(np.float32)

    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / f"wrf_{modelo}_{data}_{hora}_{dominio}_precipitacao.npz"
    np.savez_compressed(destino, lat=lat, lon=lon, tempos=tempo, chuva_horaria=incrementos)
    print(f"[OK] {destino.name} | {len(incrementos)} h | {destino.stat().st_size/2**20:.1f} MiB")
    return destino


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="Diretório POST/NETCDF")
    parser.add_argument("--saida", type=Path, default=Path("dados"))
    args = parser.parse_args()
    arquivos = sorted(args.input.glob("wrf_es_*_precip_d*.nc"))
    if not arquivos:
        parser.error(f"Nenhum arquivo simplificado encontrado em {args.input}")
    for arq in arquivos:
        exportar(arq, args.saida)


if __name__ == "__main__":
    main()
