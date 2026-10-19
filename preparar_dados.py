from pathlib import Path
import argparse
import numpy as np
from netCDF4 import Dataset


def main():
    p = argparse.ArgumentParser(description='Extrai precipitação horária de wrfout do domínio selecionado.')
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--dominio', default='d02')
    p.add_argument('--saida', type=Path, default=Path('dados/wrf_d02_precipitacao.npz'))
    args = p.parse_args()
    arquivos = sorted(args.run.glob(f'wrfout_{args.dominio}_????-??-??_??:??:??'))
    if len(arquivos) < 2:
        raise SystemExit('São necessários pelo menos dois arquivos horários wrfout.')
    tempos, acumulados = [], []
    lat = lon = None
    for idx, arquivo in enumerate(arquivos):
        with Dataset(arquivo) as ds:
            if lat is None:
                lat = np.asarray(ds.variables['XLAT'][0], dtype=np.float32)
                lon = np.asarray(ds.variables['XLONG'][0], dtype=np.float32)
            chuva = np.ma.filled(ds.variables['RAINC'][0], np.nan) + np.ma.filled(ds.variables['RAINNC'][0], np.nan)
            if chuva.shape != lat.shape:
                raise ValueError(f'Dimensões inconsistentes: {arquivo}')
            acumulados.append(np.asarray(chuva, dtype=np.float32))
            tempos.append(np.datetime64(arquivo.name.split(f'wrfout_{args.dominio}_')[1].replace('_','T')))
        if (idx + 1) % 12 == 0:
            print(f'Processados {idx+1}/{len(arquivos)} arquivos')
    tempos = np.array(tempos, dtype='datetime64[s]')
    intervalos = np.diff(tempos).astype('timedelta64[m]').astype(int)
    if np.any(intervalos != 60):
        raise ValueError(f'Arquivos não apresentam sequência horária contínua: {intervalos}')
    acumulados = np.stack(acumulados)
    incrementos = np.diff(acumulados, axis=0)
    if np.any(incrementos < -0.01):
        raise ValueError('Detectados incrementos negativos: verificar reinício dos acumuladores.')
    incrementos = np.maximum(incrementos, 0)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.saida, lat=lat, lon=lon, tempos=tempos, chuva_horaria=incrementos.astype(np.float32))
    print(f'Salvo: {args.saida} | {len(incrementos)} intervalos horários | grade {lat.shape}')

if __name__ == '__main__':
    main()
