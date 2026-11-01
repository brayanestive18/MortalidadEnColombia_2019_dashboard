"""Aplicación Streamlit: Mortalidad en Colombia 2019 (DANE, defunciones no fetales)."""
import json

import plotly.express as px
import streamlit as st

from data_loader import GEOJSON, GRUPOS_EDAD, MESES, ORDEN_EDAD, cargar_datos, nombre_causa

st.set_page_config(page_title="Mortalidad en Colombia 2019", page_icon="📊", layout="wide")

df, codigos = cargar_datos()
causas = nombre_causa(codigos)
homicidios = df[df["COD_MUERTE"].str.startswith("X95")]

st.title("Mortalidad en Colombia — 2019")
st.caption("Fuente: DANE, Estadísticas Vitales — defunciones no fetales 2019. "
           "Codificación de causas CIE-10 y división político-administrativa DIVIPOLA.")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total de muertes", f"{len(df):,}".replace(",", "."))
k2.metric("Homicidios por arma de fuego (X95)", f"{len(homicidios):,}".replace(",", "."))
k3.metric("Departamentos", df["DEPARTAMENTO"].nunique())
k4.metric("Municipios con registros", df["COD_DANE"].nunique())

# 1. Mapa por departamento
st.header("1. Distribución de muertes por departamento")
por_depto = (df.groupby(["COD_DEPARTAMENTO", "DEPARTAMENTO"]).size()
             .reset_index(name="Muertes"))
with open(GEOJSON, encoding="utf-8") as f:
    geojson = json.load(f)
fig = px.choropleth(por_depto, geojson=geojson, locations="COD_DEPARTAMENTO",
                    featureidkey="properties.DPTO", color="Muertes",
                    hover_name="DEPARTAMENTO", hover_data={"COD_DEPARTAMENTO": False},
                    color_continuous_scale="Reds")
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(height=650, margin=dict(l=0, r=0, t=0, b=0))
st.plotly_chart(fig, width="stretch")

# 2. Muertes por mes
st.header("2. Total de muertes por mes")
por_mes = df.groupby("MES").size().reindex(range(1, 13), fill_value=0).reset_index(name="Muertes")
por_mes["Mes"] = [MESES[m - 1] for m in por_mes["MES"]]
fig = px.line(por_mes, x="Mes", y="Muertes", markers=True)
fig.update_layout(yaxis_title="Número de muertes", xaxis_title=None)
st.plotly_chart(fig, width="stretch")

col1, col2 = st.columns(2)

# 3. Ciudades más violentas
with col1:
    st.header("3. Las 5 ciudades más violentas")
    st.caption("Homicidios con código CIE-10 X95: agresión con disparo de otras armas de fuego "
               "y las no especificadas.")
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
    menor = (df.groupby(["MUNICIPIO", "DEPARTAMENTO"]).size().reset_index(name="Muertes")
             .sort_values(["Muertes", "MUNICIPIO"]).head(10))
    menor["Ciudad"] = menor["MUNICIPIO"] + " (" + menor["DEPARTAMENTO"] + ")"
    fig = px.pie(menor, names="Ciudad", values="Muertes")
    fig.update_traces(textinfo="value+percent")
    st.plotly_chart(fig, width="stretch")

# 5. Principales causas de muerte
st.header("5. Las 10 principales causas de muerte")
top_causas = df["COD_MUERTE"].value_counts().head(10).reset_index()
top_causas.columns = ["Código", "Total de casos"]
top_causas.insert(1, "Causa", top_causas["Código"].map(causas))
st.dataframe(top_causas, hide_index=True, width="stretch",
             column_config={"Total de casos": st.column_config.NumberColumn(format="localized")})

# 6. Muertes por sexo en cada departamento
st.header("6. Muertes por sexo en cada departamento")
por_sexo = df.groupby(["DEPARTAMENTO", "SEXO_NOMBRE"]).size().reset_index(name="Muertes")
orden_deptos = df["DEPARTAMENTO"].value_counts().index.tolist()
fig = px.bar(por_sexo, x="DEPARTAMENTO", y="Muertes", color="SEXO_NOMBRE", barmode="stack",
             category_orders={"DEPARTAMENTO": orden_deptos,
                              "SEXO_NOMBRE": ["Masculino", "Femenino", "Indeterminado"]},
             color_discrete_map={"Masculino": "#1f6fd1", "Femenino": "#e4572e",
                                 "Indeterminado": "#9e9e9e"},
             labels={"SEXO_NOMBRE": "Sexo"})
fig.update_layout(height=600, xaxis_title=None, xaxis_tickangle=-45)
st.plotly_chart(fig, width="stretch")

# 7. Distribución por grupo de edad
st.header("7. Distribución de muertes por grupo de edad")
rangos = {nombre: rango for nombre, _, rango in GRUPOS_EDAD}
por_edad = df["GRUPO_EDAD"].value_counts().reindex(ORDEN_EDAD).reset_index()
por_edad.columns = ["Grupo de edad", "Muertes"]
por_edad["Rango"] = por_edad["Grupo de edad"].map(rangos)
fig = px.bar(por_edad, x="Grupo de edad", y="Muertes", hover_data=["Rango"], text="Muertes")
fig.update_traces(marker_line_width=0)
fig.update_layout(bargap=0.02, xaxis_title=None, xaxis_tickangle=-30)
st.plotly_chart(fig, width="stretch")
