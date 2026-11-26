"""Exporta limites continentais do ES e municípios para GeoJSON leve.

Remove Trindade e Martim Vaz e recorta quaisquer geometrias fora
da área continental ampliada, sem alterar os shapefiles originais.
"""
import argparse
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box, mapping


def escrever(path, collection):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )
    print(f"[OK] {path}: {path.stat().st_size / 1024:.0f} KiB")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cartografia", type=Path, required=True)
    p.add_argument("--saida", type=Path, default=Path("dados"))
    p.add_argument("--tolerancia", type=float, default=0.001)
    args = p.parse_args()

    caminho = args.cartografia / "municipios_es" / "ES_Municipios_2024.shp"
    df = gpd.read_file(caminho).to_crs("EPSG:4326")
    if "NM_MUN" not in df:
        raise ValueError(f"Coluna NM_MUN não encontrada: {df.columns.tolist()}")

    # Caixa ampla suficiente para todo o ES continental e ilhas costeiras.
    continental = box(-43.0, -22.0, -38.5, -17.0)
    df = df.copy()
    df["geometry"] = df.geometry.make_valid().intersection(continental)
    df = df[df.geometry.notna() & (~df.geometry.is_empty)].copy()
    if df.empty:
        raise ValueError("Recorte continental resultou vazio.")
    # GeoJSON em coordenadas WGS84; simplificação apenas para traçado.
    df["geometry"] = df.geometry.simplify(args.tolerancia, preserve_topology=True)
    df = df[~df.geometry.is_empty].copy()

    features = [
        {
            "type": "Feature",
            "properties": {"NM_MUN": str(row.NM_MUN)},
            "geometry": mapping(row.geometry),
        }
        for row in df[["NM_MUN", "geometry"]].itertuples(index=False)
    ]
    estado = df.geometry.union_all()
    # Para a máscara estatística precisa, exporta sem simplificação.
    original = gpd.read_file(caminho).to_crs("EPSG:4326")
    original["geometry"] = original.geometry.make_valid().intersection(continental)
    original = original[~original.geometry.is_empty]
    geometria_estadual = original.geometry.union_all()

    escrever(args.saida / "es_continental.geojson", {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"NM_UF": "Espírito Santo"},
                      "geometry": mapping(geometria_estadual)}],
    })
    escrever(args.saida / "municipios_es_continental.geojson", {
        "type": "FeatureCollection", "features": features,
    })
    print(f"Municípios: {len(features)} | apenas versão web, shapefiles originais preservados")


if __name__ == "__main__":
    main()
