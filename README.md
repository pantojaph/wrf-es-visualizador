# Protótipo web WRF — Evento de março de 2024

## 1. Preparar os dados no WSL

```bash
cd ~/WRF48_ES/PNT_9KM_3KM/experiments/evento_20240322_23
mkdir -p WEB/dados
# Copiar os arquivos app.py, preparar_dados.py e requirements.txt para WEB/
python -m pip install -r WEB/requirements.txt
python WEB/preparar_dados.py --run RUN --dominio d02 --saida WEB/dados/wrf_d02_precipitacao.npz
```

## 2. Abrir a aplicação local

```bash
cd WEB
python -m streamlit run app.py --server.address 127.0.0.1
```

Acessar `http://localhost:8501` no navegador do Windows.

## O que a aplicação oferece
- Acumulados móveis de 1, 3, 6, 12, 24 e 48 horas.
- Seleção do horário final em UTC.
- Mapa interativo sobre OpenStreetMap.
- Consulta por coordenadas (ponto de grade mais próximo).
- Série horária e exportação CSV.

## Limitações
- O mapa inicial desenha células da grade como pontos amostrados, não como raster georreferenciado contínuo.
- O navegador precisa de internet para carregar o mapa base do OpenStreetMap.
- Não inclui limites municipais nem validação com dados observados.
- O aplicativo é local; não está hospedado publicamente.
- O script pressupõe um arquivo por hora, com um único tempo por arquivo e acumuladores RAINC/RAINNC sem reinicializações.
- Os intervalos são definidos em UTC; chuva_horaria[k] é o acumulado de tempos[k] a tempos[k+1].
