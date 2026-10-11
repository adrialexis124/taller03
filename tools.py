"""
Lab 03 — Tools corregidas para el agente analítico (Parte 1).

Implementación que cumple estrictamente las seis reglas del taller:
- Regla 1: Esquema, nombres y descripciones claras (más herramienta de esquema).
- Regla 2: Solo lectura estricta (sqlite3 URI mode=ro, única sentencia, solo SELECT/WITH).
- Regla 3: Límites definidos por código (límite de filas forzado, carpeta fija para gráficos).
- Regla 4: Paso de datos entre herramientas (guarda data/ultimo_resultado.csv automáticamente).
- Regla 5: Captura y retorno de errores estructurados ({"error": "..."}) sin romper la ejecución.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

import matplotlib
matplotlib.use("Agg")  # Backend no interactivo para entornos headless
import matplotlib.pyplot as plt
import pandas as pd


# Regla 3: Límites definidos en el código, no en los argumentos del modelo
MAX_ROW_LIMIT = 50
CARPETA_GRAFICOS = Path("graficos")
CARPETA_GRAFICOS.mkdir(parents=True, exist_ok=True)
CSV_INTERMEDIO_DEFAULT = Path("data/ultimo_resultado.csv")


def describe_tables(db_path: str = "data/database.sqlite") -> dict:
    """
    Regla 1: Inspecciona el esquema de la base de datos SQLite.
    Devuelve las tablas existentes y los nombres y tipos de sus columnas.
    """
    try:
        path = Path(db_path)
        if not path.exists():
            return {"error": f"No existe la base de datos en: {db_path}"}

        # Regla 2: Conexión en modo solo lectura
        uri = f"file:{path.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            tablas = [r[0] for r in cursor.fetchall()]

            esquema = {}
            for tabla in tablas:
                cursor.execute(f'PRAGMA table_info("{tabla}")')
                columnas = [{"nombre": col[1], "tipo": col[2]} for col in cursor.fetchall()]
                esquema[tabla] = columnas

        return {"tablas": tablas, "esquema": esquema}
    except Exception as e:
        # Regla 5: El error no aborta la ejecución
        return {"error": f"Error al inspeccionar tablas: {str(e)}"}


def execute_query(query: str, db_path: str = "data/database.sqlite") -> dict:
    """
    Regla 2: Ejecuta una consulta SQL exclusivamente de solo lectura sobre la base de datos.
    Regla 3: Aplica un límite forzado de máximo 50 filas sin permitir evasión.
    Regla 4: Guarda los resultados en data/ultimo_resultado.csv para que otras herramientas los consuman.
    """
    try:
        # Regla 2: Validación estricta de solo lectura y sentencia única
        sentencia = query.strip()
        if not sentencia:
            return {"error": "La consulta SQL no puede estar vacía."}

        # Comprobar que no haya sentencias múltiples separadas por ';'
        sentencia_sin_final = sentencia.rstrip(";")
        if ";" in sentencia_sin_final:
            return {"error": "Solo se permite una única sentencia SQL por ejecución (múltiples declaraciones detectadas)."}

        normalizada = sentencia_sin_final.lower()
        if not (normalizada.startswith("select") or normalizada.startswith("with")):
            return {"error": "Solo se permiten consultas que inicien con SELECT o WITH en este entorno analítico."}

        # Rechazo de palabras clave de modificación
        tokens_prohibidos = [
            r"\binsert\b", r"\bupdate\b", r"\bdelete\b", r"\bdrop\b",
            r"\balter\b", r"\bcreate\b", r"\battach\b", r"\bdetach\b",
            r"\bpragma\b", r"\breplace\b"
        ]
        for token in tokens_prohibidos:
            if re.search(token, normalizada):
                return {"error": f"Consulta rechazada: contiene operaciones no autorizadas ({token.replace(r'\b', '')})."}

        path = Path(db_path)
        if not path.exists():
            return {"error": f"No existe la base de datos en: {db_path}"}

        # Regla 3: Envolver la consulta para garantizar que el límite no sea superado por el modelo
        consulta_delimitada = f"SELECT * FROM ({sentencia_sin_final}) LIMIT {MAX_ROW_LIMIT}"

        # Regla 2: Apertura con sqlite3 en modo solo lectura explícito
        uri = f"file:{path.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            frame = pd.read_sql_query(consulta_delimitada, conn)

        # Regla 4: Pasar datos entre herramientas guardando el resultado en un archivo CSV intermedio
        CSV_INTERMEDIO_DEFAULT.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(CSV_INTERMEDIO_DEFAULT, index=False)

        return {
            "columns": list(frame.columns),
            "rows": frame.to_dict(orient="records"),
            "row_count": len(frame),
            "csv_guardado": str(CSV_INTERMEDIO_DEFAULT),
        }
    except Exception as e:
        # Regla 5: Manejo robusto de errores
        return {"error": f"Error ejecutando SQL: {str(e)}"}


def compute_statistics(csv_path: str = "data/ultimo_resultado.csv", columns: list[str] | None = None) -> dict:
    """
    Regla 4: Calcula estadísticas descriptivas (media, mediana, dispersión) sobre un dataset tabular.
    Usa por defecto data/ultimo_resultado.csv proveniente de la última consulta.
    """
    try:
        path = Path(csv_path)
        if not path.exists():
            return {"error": f"No existe el archivo de datos: {csv_path}. Ejecuta primero una consulta con execute_query."}

        # Regla 3: Prevenir path traversal fuera del directorio del proyecto
        if ".." in path.parts:
            return {"error": "Ruta no permitida (no se permite navegación con '..')."}

        frame = pd.read_csv(path)
        if frame.empty:
            return {"error": "El conjunto de datos está vacío."}

        numeric = frame.select_dtypes(include="number")
        if numeric.empty:
            return {"error": "El archivo no contiene columnas numéricas para calcular estadísticas."}

        if columns:
            missing = [column for column in columns if column not in numeric.columns]
            if missing:
                return {"error": f"Columnas numéricas no encontradas: {missing}. Disponibles: {list(numeric.columns)}"}
            numeric = numeric[columns]

        estadisticas = numeric.describe().to_dict()
        # Agregar la mediana explícita si describe() no la nombra directamente como median
        medianas = numeric.median().to_dict()
        for col in medianas:
            if col in estadisticas:
                estadisticas[col]["median"] = medianas[col]

        return {"columnas_analizadas": list(numeric.columns), "estadisticas": estadisticas}
    except Exception as e:
        # Regla 5: Error seguro
        return {"error": f"Error calculando estadísticas: {str(e)}"}


def generate_chart(
    x: str,
    y: str,
    chart_type: str = "line",
    csv_path: str = "data/ultimo_resultado.csv",
    title: str = "Gráfico",
    **kwargs,
) -> dict:
    """
    Regla 3: Genera una visualización y la almacena en una carpeta fija ('graficos/').
    El modelo no decide la ruta de guardado ni puede sobrescribir archivos previos.
    Regla 4: Usa por defecto la salida de la consulta previa (data/ultimo_resultado.csv).
    """
    try:
        path = Path(csv_path)
        if not path.exists():
            return {"error": f"No existe el archivo: {csv_path}. Ejecuta primero una consulta con execute_query."}

        if ".." in path.parts:
            return {"error": "Ruta no permitida (no se permite navegación con '..')."}

        frame = pd.read_csv(path)
        if x not in frame.columns or y not in frame.columns:
            return {"error": f"Columnas inválidas. Columnas disponibles: {list(frame.columns)}"}

        # Regla 3: La ruta de salida la controla el código en CARPETA_GRAFICOS con nombre único
        id_unico = uuid.uuid4().hex[:6]
        timestamp = int(time.time())
        nombre_archivo = f"chart_{timestamp}_{id_unico}.png"
        ruta_salida = CARPETA_GRAFICOS / nombre_archivo

        plt.figure(figsize=(8, 4))
        if chart_type == "bar":
            plt.bar(frame[x].astype(str), frame[y])
        elif chart_type == "scatter":
            plt.scatter(frame[x], frame[y])
        else:
            plt.plot(frame[x].astype(str), frame[y], marker="o")

        plt.xlabel(x)
        plt.ylabel(y)
        plt.title(title)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(ruta_salida)
        plt.close()

        return {
            "chart_path": str(ruta_salida),
            "chart_type": chart_type,
            "x": x,
            "y": y,
            "status": "guardado_exitosamente",
        }
    except Exception as e:
        # Regla 5: Manejo de errores
        return {"error": f"Error generando gráfico: {str(e)}"}


# Regla 1: Registro de herramientas y esquema explícito para el modelo
TOOL_REGISTRY = {
    "describe_tables": describe_tables,
    "execute_query": execute_query,
    "compute_statistics": compute_statistics,
    "generate_chart": generate_chart,
}

TOOLS_METADATA = [
    {
        "name": "describe_tables",
        "description": "Inspecciona el esquema de la base de datos SQLite. Devuelve la lista de tablas y las columnas (nombre y tipo) de cada una.",
        "parameters": {
            "type": "object",
            "properties": {
                "db_path": {"type": "string", "description": "Ruta a la base de datos (por defecto 'data/database.sqlite')"}
            },
            "required": [],
        },
    },
    {
        "name": "execute_query",
        "description": "Ejecuta una consulta SQL de solo lectura (SELECT o WITH). Guarda automáticamente el resultado en 'data/ultimo_resultado.csv' para que las herramientas de estadísticas y gráficos puedan utilizarlo.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta SQL (solo SELECT o WITH, sin modificaciones ni punto y coma adicional)."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "compute_statistics",
        "description": "Calcula estadísticas descriptivas (media, mediana, desviación estándar, min, max) sobre columnas numéricas de un CSV. Por defecto analiza 'data/ultimo_resultado.csv'.",
        "parameters": {
            "type": "object",
            "properties": {
                "csv_path": {"type": "string", "description": "Ruta al archivo CSV (por defecto 'data/ultimo_resultado.csv')"},
                "columns": {"type": "array", "items": {"type": "string"}, "description": "Lista opcional de nombres de columnas a calcular."}
            },
            "required": [],
        },
    },
    {
        "name": "generate_chart",
        "description": "Genera una visualización gráfica (line, bar, o scatter) y la guarda de forma segura en la carpeta 'graficos/'. Usa por defecto 'data/ultimo_resultado.csv'.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "string", "description": "Nombre de la columna para el eje X."},
                "y": {"type": "string", "description": "Nombre de la columna numérica para el eje Y."},
                "chart_type": {"type": "string", "enum": ["line", "bar", "scatter"], "description": "Tipo de gráfico ('line', 'bar', 'scatter'). Por defecto 'line'."},
                "csv_path": {"type": "string", "description": "Ruta al CSV con los datos (por defecto 'data/ultimo_resultado.csv')."},
                "title": {"type": "string", "description": "Título del gráfico."}
            },
            "required": ["x", "y"],
        },
    },
]
