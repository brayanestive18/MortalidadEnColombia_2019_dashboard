"""Carga, limpieza y unión de los datos de mortalidad no fetal 2019 (DANE)."""
from pathlib import Path

import pandas as pd
import streamlit as st

BASE = Path(__file__).parent
DATA = BASE / "data"
F_MUERTES = BASE / "Anexo1.NoFetal2019_CE_15-03-23.xlsx"
F_CODIGOS = BASE / "Anexo2.CodigosDeMuerte_CE_15-03-23.xlsx"
F_DIVIPOLA = BASE / "Divipola_CE_.xlsx"
GEOJSON = DATA / "colombia_departamentos.geojson"

SEXOS = {"1": "Masculino", "2": "Femenino", "3": "Indeterminado"}

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Rangos de GRUPO_EDAD1 según la tabla de referencia
GRUPOS_EDAD = [
    ("Mortalidad neonatal", range(0, 5), "Menor de 1 mes"),
    ("Mortalidad infantil", range(5, 7), "1 a 11 meses"),
    ("Primera infancia", range(7, 9), "1 a 4 años"),
    ("Niñez", range(9, 11), "5 a 14 años"),
    ("Adolescencia", range(11, 12), "15 a 19 años"),
    ("Juventud", range(12, 14), "20 a 29 años"),
    ("Adultez temprana", range(14, 17), "30 a 44 años"),
    ("Adultez intermedia", range(17, 20), "45 a 59 años"),
    ("Vejez", range(20, 25), "60 a 84 años"),
    ("Longevidad / Centenarios", range(25, 29), "85 a 100+ años"),
    ("Edad desconocida", range(29, 30), "Sin información"),
]
ORDEN_EDAD = [nombre for nombre, _, _ in GRUPOS_EDAD]
CODIGO_A_EDAD = {c: nombre for nombre, rango, _ in GRUPOS_EDAD for c in rango}


def _cache_parquet(nombre, construir):
    """Lee data/<nombre>.parquet si existe; si no, lo construye desde Excel y lo guarda."""
    ruta = DATA / f"{nombre}.parquet"
    if ruta.exists():
        return pd.read_parquet(ruta)
    df = construir()
    DATA.mkdir(exist_ok=True)
    df.to_parquet(ruta, index=False)
    return df


def _leer_divipola():
    df = pd.read_excel(F_DIVIPOLA, sheet_name="Hoja1", dtype=str)
    df = df[["COD_DANE", "COD_DEPARTAMENTO", "DEPARTAMENTO", "MUNICIPIO"]].dropna(subset=["COD_DANE"])
    df["COD_DANE"] = df["COD_DANE"].str.strip().str.zfill(5)
    df["COD_DEPARTAMENTO"] = df["COD_DEPARTAMENTO"].str.strip().str.zfill(2)
    return df.drop_duplicates("COD_DANE")


def _leer_codigos():
    df = pd.read_excel(F_CODIGOS, sheet_name="Final", skiprows=8, dtype=str)
    df = df.iloc[:, 2:6]
    df.columns = ["COD3", "DESC3", "COD4", "DESC4"]
    return df.dropna(subset=["COD4"]).apply(lambda s: s.str.strip())


def _leer_muertes():
    cols = ["COD_DANE", "COD_DEPARTAMENTO", "MES", "SEXO", "GRUPO_EDAD1", "MANERA_MUERTE", "COD_MUERTE"]
    df = pd.read_excel(F_MUERTES, sheet_name="No_Fetales_2019", usecols=cols, dtype=str)
    df["COD_DANE"] = df["COD_DANE"].str.strip().str.zfill(5)
    df["COD_DEPARTAMENTO"] = df["COD_DEPARTAMENTO"].str.strip().str.zfill(2)
    df["COD_MUERTE"] = df["COD_MUERTE"].str.strip().str.upper()
    df["MES"] = pd.to_numeric(df["MES"], errors="coerce").astype("Int64")
    df["GRUPO_EDAD1"] = pd.to_numeric(df["GRUPO_EDAD1"], errors="coerce").astype("Int64")
    return df


@st.cache_data(show_spinner="Cargando datos de mortalidad…")
def cargar_datos():
    """Devuelve (muertes, codigos) con nombres de departamento/municipio, sexo y grupo de edad."""
    muertes = _cache_parquet("muertes", _leer_muertes)
    divipola = _cache_parquet("divipola", _leer_divipola)
    codigos = _cache_parquet("codigos", _leer_codigos)

    deptos = divipola.drop_duplicates("COD_DEPARTAMENTO")[["COD_DEPARTAMENTO", "DEPARTAMENTO"]].copy()
    deptos["DEPARTAMENTO"] = deptos["DEPARTAMENTO"].replace(
        {"ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA": "SAN ANDRÉS Y PROVIDENCIA"})
    df = (muertes
          .merge(divipola[["COD_DANE", "MUNICIPIO"]], on="COD_DANE", how="left")
          .merge(deptos, on="COD_DEPARTAMENTO", how="left"))
    df["SEXO_NOMBRE"] = df["SEXO"].map(SEXOS).fillna("Indeterminado")
    df["GRUPO_EDAD"] = pd.Categorical(
        df["GRUPO_EDAD1"].map(CODIGO_A_EDAD).fillna("Edad desconocida"),
        categories=ORDEN_EDAD, ordered=True)
    return df, codigos


def nombre_causa(codigos):
    """Diccionario código -> descripción (4 caracteres, con respaldo a 3 caracteres)."""
    nombres = dict(zip(codigos["COD3"], codigos["DESC3"]))
    nombres.update(zip(codigos["COD4"], codigos["DESC4"]))
    return nombres
