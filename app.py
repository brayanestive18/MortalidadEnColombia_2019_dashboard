"""Aplicación Streamlit: Mortalidad en Colombia 2019 (DANE, defunciones no fetales)."""
import json

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_loader import GEOJSON, GRUPOS_EDAD, MESES, ORDEN_EDAD, cargar_datos, nombre_causa

st.set_page_config(page_title="Mortalidad en Colombia 2019", page_icon="📊", layout="wide")

df, codigos = cargar_datos()
causas = nombre_causa(codigos)

# --- Filtros compartidos -------------------------------------------------------
# Cada filtro vive en st.session_state (clave = columna del DataFrame). Los selectores
# del panel lateral y los clics en las gráficas modifican el mismo estado.
FILTROS = {
    "DEPARTAMENTO": "Departamento",
    "MES": "Mes",
    "SEXO_NOMBRE": "Sexo",
    "GRUPO_EDAD": "Grupo de edad",
    "MANERA_MUERTE": "Manera de muerte",
    "COD_MUERTE": "Causa (CIE-10)",
}
for col in FILTROS:
    st.session_state.setdefault(col, [])
st.session_state.setdefault("version", 0)  # cambia la key de las gráficas para limpiar su selección


def alternar(col, valor):
    """Agrega el valor al filtro, o lo quita si ya estaba."""
    actual = list(st.session_state[col])
    st.session_state[col] = [v for v in actual if v != valor] if valor in actual else actual + [valor]
    st.session_state.version += 1


def limpiar_filtros():
    for col in FILTROS:
        st.session_state[col] = []
    st.session_state.version += 1


def al_hacer_clic(key, col, extraer):
    """Callback para gráficas Plotly: convierte el punto clicado en un valor de filtro."""
    def callback():
        for punto in st.session_state[key].selection.points:
            alternar(col, extraer(punto))
    return callback


def filtrar(excluir=()):
    """Aplica todos los filtros activos salvo los indicados en `excluir`."""
    mascara = True
    for col in FILTROS:
        valores = st.session_state[col]
        if valores and col not in excluir:
            mascara = mascara & df[col].isin(valores)
    return df if mascara is True else df[mascara]


def k(nombre):
    return f"{nombre}_{st.session_state.version}"


with st.sidebar:
    st.header("Filtros")
    st.caption("También puedes hacer clic en el mapa, la línea de meses, las barras por sexo, "
               "el histograma de edad o una fila de la tabla de causas. "
               "Un segundo clic quita el filtro.")
    st.multiselect("Departamento", sorted(df["DEPARTAMENTO"].unique()), key="DEPARTAMENTO")
    st.multiselect("Mes", list(range(1, 13)), format_func=lambda m: MESES[m - 1], key="MES")
    st.multiselect("Sexo", ["Masculino", "Femenino", "Indeterminado"], key="SEXO_NOMBRE")
    st.multiselect("Grupo de edad", ORDEN_EDAD, key="GRUPO_EDAD")
    st.multiselect("Manera de muerte", sorted(df["MANERA_MUERTE"].dropna().unique()),
                   key="MANERA_MUERTE")
    st.multiselect("Causa (CIE-10)", df["COD_MUERTE"].value_counts().index.tolist(),
                   format_func=lambda c: f"{c} — {causas.get(c, 'Sin descripción')}",
                   key="COD_MUERTE")
    st.button("Limpiar filtros", on_click=limpiar_filtros, width="stretch")

datos = filtrar()
homicidios = filtrar(excluir=["COD_MUERTE"])
homicidios = homicidios[homicidios["COD_MUERTE"].str.startswith("X95")]

st.title("Mortalidad en Colombia — 2019")
st.caption("Fuente: DANE, Estadísticas Vitales — defunciones no fetales 2019. "
           "Codificación de causas CIE-10 y división político-administrativa DIVIPOLA.")

activos = [f"**{FILTROS[c]}:** " + ", ".join(
    MESES[v - 1] if c == "MES" else str(v) for v in st.session_state[c])
    for c in FILTROS if st.session_state[c]]
if activos:
    st.info("Filtros activos — " + " · ".join(activos))

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total de muertes", f"{len(datos):,}".replace(",", "."))
k2.metric("Homicidios por arma de fuego (X95)", f"{len(homicidios):,}".replace(",", "."))
k3.metric("Departamentos", datos["DEPARTAMENTO"].nunique())
k4.metric("Municipios con registros", datos["COD_DANE"].nunique())

if datos.empty:
    st.warning("No hay registros para la combinación de filtros seleccionada.")
    st.stop()

# 1. Mapa por departamento (ignora su propio filtro para poder seguir eligiendo departamentos)
st.header("1. Distribución de muertes por departamento")
st.caption("Haz clic en un departamento para filtrar el resto de la página.")
por_depto = (filtrar(excluir=["DEPARTAMENTO"]).groupby(["COD_DEPARTAMENTO", "DEPARTAMENTO"])
             .size().reset_index(name="Muertes"))
seleccion = por_depto["DEPARTAMENTO"].isin(st.session_state.DEPARTAMENTO)
with open(GEOJSON, encoding="utf-8") as f:
    geojson = json.load(f)
fig = px.choropleth(por_depto, geojson=geojson, locations="COD_DEPARTAMENTO",
                    featureidkey="properties.DPTO", color="Muertes",
                    hover_name="DEPARTAMENTO", hover_data={"COD_DEPARTAMENTO": False},
                    custom_data=["DEPARTAMENTO"], color_continuous_scale="Reds")
fig.update_traces(marker_line_width=[3 if s else 0.5 for s in seleccion],
                  marker_line_color=["#111" if s else "#666" for s in seleccion])
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(height=650, margin=dict(l=0, r=0, t=0, b=0), clickmode="event+select")
st.plotly_chart(fig, width="stretch", key=k("mapa"), selection_mode="points",
                on_select=al_hacer_clic(k("mapa"), "DEPARTAMENTO", lambda p: p["customdata"][0]))

# 2. Muertes por mes
st.header("2. Total de muertes por mes")
por_mes = (filtrar(excluir=["MES"]).groupby("MES").size()
           .reindex(range(1, 13), fill_value=0).reset_index(name="Muertes"))
por_mes["Mes"] = [MESES[m - 1] for m in por_mes["MES"]]
fig = px.line(por_mes, x="Mes", y="Muertes", markers=True)
elegidos = por_mes[por_mes["MES"].isin(st.session_state.MES)]
if not elegidos.empty:
    fig.add_trace(go.Scatter(x=elegidos["Mes"], y=elegidos["Muertes"], mode="markers",
                             marker=dict(size=16, color="#e4572e"), hoverinfo="skip",
                             showlegend=False))
fig.update_layout(yaxis_title="Número de muertes", xaxis_title=None)
st.plotly_chart(fig, width="stretch", key=k("meses"), selection_mode="points",
                on_select=al_hacer_clic(k("meses"), "MES", lambda p: MESES.index(p["x"]) + 1))

col1, col2 = st.columns(2)

# 3. Ciudades más violentas
with col1:
    st.header("3. Las 5 ciudades más violentas")
    st.caption("Homicidios con código CIE-10 X95: agresión con disparo de otras armas de fuego "
               "y las no especificadas. No usa el filtro de causa.")
    if homicidios.empty:
        st.info("No hay homicidios X95 con los filtros actuales.")
    else:
        top_violentas = (homicidios.groupby("MUNICIPIO").size().nlargest(5)
                         .reset_index(name="Homicidios"))
        fig = px.bar(top_violentas, x="MUNICIPIO", y="Homicidios", text="Homicidios",
                     color="Homicidios", color_continuous_scale="Reds")
        fig.update_layout(xaxis_title=None, coloraxis_showscale=False)
        st.plotly_chart(fig, width="stretch")

# 4. Ciudades con menor mortalidad
with col2:
    st.header("4. Las 10 ciudades con menor mortalidad")
    st.caption("Municipios con menos muertes registradas (valores absolutos; empates ordenados "
               "alfabéticamente).")
    menor = (datos.groupby(["MUNICIPIO", "DEPARTAMENTO"]).size().reset_index(name="Muertes")
             .sort_values(["Muertes", "MUNICIPIO"]).head(10))
    menor["Ciudad"] = menor["MUNICIPIO"] + " (" + menor["DEPARTAMENTO"] + ")"
    fig = px.pie(menor, names="Ciudad", values="Muertes")
    fig.update_traces(textinfo="value+percent")
    st.plotly_chart(fig, width="stretch")

# 5. Principales causas de muerte (ignora el filtro de causa; las elegidas se marcan)
st.header("5. Las 10 principales causas de muerte")
st.caption("Selecciona una fila para filtrar por esa causa.")
top_causas = filtrar(excluir=["COD_MUERTE"])["COD_MUERTE"].value_counts().head(10).reset_index()
top_causas.columns = ["Código", "Total de casos"]
top_causas.insert(1, "Causa", top_causas["Código"].map(causas))
top_causas.insert(0, "Filtro", top_causas["Código"].isin(st.session_state.COD_MUERTE))


def al_elegir_causa(key=k("causas"), codigos_tabla=top_causas["Código"].tolist()):
    for fila in st.session_state[key].selection.rows:
        alternar("COD_MUERTE", codigos_tabla[fila])


st.dataframe(top_causas, hide_index=True, width="stretch", key=k("causas"),
             on_select=al_elegir_causa, selection_mode="single-row",
             column_config={"Total de casos": st.column_config.NumberColumn(format="localized"),
                            "Filtro": st.column_config.CheckboxColumn(width="small")})

# 6. Muertes por sexo en cada departamento (ignora el filtro de sexo; resalta el elegido)
st.header("6. Muertes por sexo en cada departamento")
st.caption("Haz clic en un segmento para filtrar por ese sexo.")
base_sexo = filtrar(excluir=["SEXO_NOMBRE"])
por_sexo = base_sexo.groupby(["DEPARTAMENTO", "SEXO_NOMBRE"]).size().reset_index(name="Muertes")
orden_deptos = base_sexo["DEPARTAMENTO"].value_counts().index.tolist()
fig = px.bar(por_sexo, x="DEPARTAMENTO", y="Muertes", color="SEXO_NOMBRE", barmode="stack",
             custom_data=["SEXO_NOMBRE"],
             category_orders={"DEPARTAMENTO": orden_deptos,
                              "SEXO_NOMBRE": ["Masculino", "Femenino", "Indeterminado"]},
             color_discrete_map={"Masculino": "#1f6fd1", "Femenino": "#e4572e",
                                 "Indeterminado": "#9e9e9e"},
             labels={"SEXO_NOMBRE": "Sexo"})
if st.session_state.SEXO_NOMBRE:
    fig.for_each_trace(lambda t: t.update(
        opacity=1 if t.name in st.session_state.SEXO_NOMBRE else 0.25))
fig.update_layout(height=600, xaxis_title=None, xaxis_tickangle=-45)
st.plotly_chart(fig, width="stretch", key=k("sexo"), selection_mode="points",
                on_select=al_hacer_clic(k("sexo"), "SEXO_NOMBRE", lambda p: p["customdata"][0]))

# 7. Distribución por grupo de edad (ignora el filtro de edad; resalta los elegidos)
st.header("7. Distribución de muertes por grupo de edad")
st.caption("Haz clic en una barra para filtrar por ese grupo de edad.")
rangos = {nombre: rango for nombre, _, rango in GRUPOS_EDAD}
por_edad = filtrar(excluir=["GRUPO_EDAD"])["GRUPO_EDAD"].value_counts().reindex(ORDEN_EDAD).reset_index()
por_edad.columns = ["Grupo de edad", "Muertes"]
por_edad["Rango"] = por_edad["Grupo de edad"].map(rangos)
fig = px.bar(por_edad, x="Grupo de edad", y="Muertes", hover_data=["Rango"], text="Muertes")
if st.session_state.GRUPO_EDAD:
    fig.update_traces(marker_color=["#e4572e" if g in st.session_state.GRUPO_EDAD else "#9ec5f0"
                                    for g in por_edad["Grupo de edad"]])
fig.update_traces(marker_line_width=0)
fig.update_layout(bargap=0.02, xaxis_title=None, xaxis_tickangle=-30)
st.plotly_chart(fig, width="stretch", key=k("edad"), selection_mode="points",
                on_select=al_hacer_clic(k("edad"), "GRUPO_EDAD", lambda p: p["x"]))
