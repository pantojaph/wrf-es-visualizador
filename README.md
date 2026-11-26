# WRF-ES | Visualizador de precipitação

Visualizador Streamlit de campos de precipitação do **WRF-ARW 4.8.0**, com suporte ao experimento histórico de março de 2024 e às rodadas de novembro de 2026 (GFS; preparado também para ECMWF).

## Melhorias cartográficas

- Campo contínuo com `matplotlib.contourf` (em vez de pontos amostrados).
- Limiar visual: **acumulados inferiores a 1 mm ficam em branco**.
- Escala fixa: 1, 5, 10, 20, 30, 50, 75, 100, 150, 200, 300, 400 e 500 mm.
- Recorte do ES continental (retira Trindade e Martim Vaz) e limites municipais.
- Extensão estadual fixa: 42,3°W–39,3°W; 21,5°S–17,5°S.
- Cálculos sobre a grade original, **sem filtro gaussiano, suavização numérica ou subamostragem**.
- Seleção de rodada, domínio, horizonte temporal, consulta por coordenadas e série horária em BRT.

O histórico continua funcionando com `dados/wrf_d02_precipitacao.npz`. Quando a cartografia continental ainda não tiver sido exportada, a aplicação desativa a estatística estadual e permite ver o domínio inteiro.

## 1. Preparar o projeto localmente (WSL2)

```bash
cd ~/WRF48_ES
git clone https://github.com/pantojaph/wrf-es-visualizador.git
cd wrf-es-visualizador
git checkout feat/wrf-es-precipitation-maps-202611
source ~/WRF48_ES/ENVIRONMENTS/wrf_analysis/bin/activate
python -m pip install -r requirements.txt
```

Se o clone já existir, execute `git fetch origin` seguido de `git switch feat/wrf-es-precipitation-maps-202611`.

## 2. Exportar as rodadas GFS de 25/11/2026

O projeto **não consegue ler diretamente o WSL2 do computador doméstico** quando está hospedado na nuvem. Exporte os NetCDFs simplificados para NPZ e inclua os arquivos no repositório.

```bash
BASE="$HOME/WRF48_ES/PNT_9KM_3KM/experiments/evento_20261125_28"
python exportar_rodada.py \
  --input "$BASE/GFS/20261125_12/POST/NETCDF" \
  --saida dados
```

Arquivos esperados:

```text
dados/wrf_gfs_20261125_12_d01_precipitacao.npz
dados/wrf_gfs_20261125_12_d02_precipitacao.npz
```

O exportador verifica sequência horária, integridade e a correspondência entre a precipitação horária e os acumulados.

## 3. Exportar limites continentais do Espírito Santo

```bash
python exportar_cartografia.py \
  --cartografia "$HOME/WRF48_ES/CARTOGRAFIA" \
  --saida dados
```

Serão criados `dados/es_continental.geojson` (geometria estadual sem simplificação) e `dados/municipios_es_continental.geojson` (geometrias simplificadas **apenas para o desenho**). Não altera os shapefiles originais. A redução da complexidade dos limites evita sobrecarregar a aplicação Streamlit.

## 4. Testar localmente

```bash
python -m streamlit run app.py
```

Acesse `http://localhost:8501` e confira:

1. Seleção do histórico março/2024 e da rodada GFS novembro/2026 (d01 e d02).
2. Campo contínuo e regiões de chuva <1 mm brancas.
3. Máximo estadual diferente do máximo do domínio quando pertinente.
4. Ponto consultado, evolução horária e CSV.
5. Mapas de 72 e 90 horas, em particular a área do Caparaó.

## 5. Enviar os dados ao GitHub e publicar

Depois de testar, confirme os arquivos e tamanhos:

```bash
ls -lh dados/*.npz dados/*.geojson
git status --short
git add app.py exportar_rodada.py exportar_cartografia.py requirements.txt README.md .gitignore dados/
git commit -m "data: adicionar previsão WRF-GFS novembro 2026 e cartografia ES"
git push origin feat/wrf-es-precipitation-maps-202611
```

Se a branch já foi publicada pelo conector, o `git push` adicionará apenas os dados gerados no seu computador. Revise previamente o tamanho dos arquivos; o GitHub limita cada arquivo comum a 100 MiB e a implantação Streamlit tem limites próprios de armazenamento e memória.

Abra ou atualize o pull request da branch e revise as imagens antes de mesclar com `main`. No Streamlit Community Cloud, a atualização em `main` será aplicada conforme a configuração do aplicativo. Caso a implantação esteja apontando para outra branch, altere-a nas configurações do serviço.

## Notas metodológicas

- Cada `chuva_horaria[k]` representa o intervalo `(tempos[k], tempos[k+1]]` em mm.
- As cores e contornos são uma opção **gráfica**, e não uma interpolação dos dados de avaliação.
- A localização do máximo estadual usa o centro da célula dentro do limite continental.
- A precipitação simulada não equivale a uma observação e não está validada.
- A mudança cartográfica não modifica os arquivos `wrfout` nem o NetCDF simplificado.
