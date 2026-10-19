from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='WRF | Evento março de 2024', page_icon='🌧️', layout='wide')
st.title('WRF | Evento de precipitação — março de 2024')
st.caption('Experimento histórico WRF-ARW 4.8.0 · D02 3 km · Horários em UTC · Dados simulados, não observados')

ARQUIVO = Path(__file__).resolve().parent / 'dados' / 'wrf_d02_precipitacao.npz'
if not ARQUIVO.exists():
    st.warning('Base processada não encontrada. Execute preparar_dados.py conforme README.md.')
    st.stop()

@st.cache_data(show_spinner='Carregando dados processados...')
def carregar(caminho):
    with np.load(caminho) as z:
        return (z['lat'], z['lon'], z['tempos'].astype('datetime64[s]'), z['chuva_horaria'])

lat, lon, tempos, chuva = carregar(str(ARQUIVO))
# Cada incremento chuva[k] cobre (tempos[k], tempos[k+1]].
instantes = pd.to_datetime(tempos[1:]).tz_localize('UTC')

with st.sidebar:
    st.header('Controles')
    janela = st.selectbox('Acumulado', [1, 3, 6, 12, 24, 48], index=4, format_func=lambda h: f'{h} horas')
    possiveis = list(range(janela - 1, len(instantes)))
    if not possiveis:
        st.error('A série não cobre a janela escolhida.')
        st.stop()
    k = st.select_slider('Horário final (UTC)', options=possiveis, value=possiveis[-1],
                         format_func=lambda i: instantes[i].strftime('%d/%m %H:%M'))
    passo = st.select_slider('Amostragem para visualização', options=[1,2,3,4], value=2,
                            help='Reduz apenas a quantidade de pontos desenhados; cálculos preservam a grade original.')
    st.divider()
    st.subheader('Consulta por coordenadas')
    consulta_lat = st.number_input('Latitude', value=-21.064, format='%.4f')
    consulta_lon = st.number_input('Longitude', value=-41.366, format='%.4f')

inicio = k - janela + 1
campo = np.nansum(chuva[inicio:k+1], axis=0)
# Haversine: ponto mais próximo da coordenada consultada.
phi1 = np.radians(consulta_lat)
phi2 = np.radians(lat)
dphi = phi2 - phi1
dlon = np.radians(lon - consulta_lon)
a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlon/2)**2
dist = 2*6371*np.arcsin(np.sqrt(np.clip(a,0,1)))
j, i = np.unravel_index(np.nanargmin(dist), dist.shape)

col1, col2, col3 = st.columns(3)
col1.metric('Máximo no domínio', f'{np.nanmax(campo):.1f} mm')
col2.metric('No ponto consultado', f'{campo[j,i]:.1f} mm')
col3.metric('Distância até o ponto de grade', f'{dist[j,i]:.2f} km')

esq, dir = st.columns([1.5,1])
with esq:
    st.subheader(f'Precipitação acumulada · {janela} h')
    amostra = campo[::passo, ::passo]
    xs, ys = lon[::passo, ::passo], lat[::passo, ::passo]
    validos = np.isfinite(amostra) & (amostra >= 1)
    fig = go.Figure()
    fig.add_trace(go.Scattermap(
        lat=ys[validos].ravel(), lon=xs[validos].ravel(), mode='markers',
        marker={'size': 6 if passo == 1 else 9, 'color': amostra[validos].ravel(),
                'colorscale': 'Turbo', 'cmin': 0, 'cmax': 200, 'opacity': 0.78,
                'colorbar': {'title': 'mm'}},
        customdata=amostra[validos].ravel(),
        hovertemplate='Lat %{lat:.3f}<br>Lon %{lon:.3f}<br>Chuva %{customdata:.1f} mm<extra></extra>',
        name='WRF'))
    fig.add_trace(go.Scattermap(lat=[float(lat[j,i])], lon=[float(lon[j,i])], mode='markers',
        marker={'size': 13, 'color': 'black'}, name='Ponto consultado'))
    fig.update_layout(map={'style': 'open-street-map', 'center': {'lat': -20.7, 'lon': -41.3}, 'zoom': 6.5},
                      margin=dict(l=0,r=0,t=0,b=0), height=610, legend={'orientation':'h'})
    st.plotly_chart(fig, use_container_width=True)
    st.caption('Pontos coloridos representam células amostradas da grade WRF, não um raster contínuo. Áreas sem pontos podem ter chuva inferior a 1 mm.')
with dir:
    st.subheader('Série horária no ponto selecionado')
    serie = pd.DataFrame({'Horário UTC': instantes, 'Precipitação (mm)': chuva[:,j,i]})
    barras = go.Figure(go.Bar(x=serie['Horário UTC'], y=serie['Precipitação (mm)']))
    barras.update_layout(xaxis_title='Horário final do intervalo (UTC)', yaxis_title='mm/h', height=350,
                        margin=dict(l=20,r=20,t=10,b=40))
    st.plotly_chart(barras, use_container_width=True)
    st.write(f'Ponto WRF: {lat[j,i]:.4f}, {lon[j,i]:.4f} · grade j={j}, i={i}')
    st.download_button('Baixar série horária CSV', data=serie.to_csv(index=False).encode('utf-8-sig'),
                       file_name='serie_horaria_wrf.csv', mime='text/csv')

st.info('Esta é uma primeira versão de exploração científica. Não representa validação do modelo; a comparação com observações será adicionada posteriormente.')
