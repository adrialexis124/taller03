"""
Lab 03 — Script de demostración para la Parte 3 (Frenos).

Ejecuta tres pruebas controladas mediante un agente con salidas de guion
para hacer saltar cada uno de los tres frenos sin costo de API y generar sus trazas:
1. Máximo de pasos (max_steps_reached)
2. Presupuesto de tokens por corrida (budget_exceeded)
3. Detector de repetición (repetition_detected)

Uso:
    python probar_frenos.py           # Corre los tres frenos secuencialmente
    python probar_frenos.py pasos     # Solo freno 1
    python probar_frenos.py tokens    # Solo freno 2
    python probar_frenos.py repeticion # Solo freno 3
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from agent import AnalystAgent


class AgenteFrenosGuion(AnalystAgent):
    """
    Agente que simula respuestas del LLM con tokens y acciones controladas
    para probar y hacer saltar cada freno de forma determinista.
    """

    def __init__(self, guion: list[tuple[dict, int, int]], **kwargs):
        super().__init__(model="guion_frenos", **kwargs)
        self._guion = list(guion)

    def _call_llm(self, messages):
        if self._guion:
            item = self._guion.pop(0)
            return item  # (parsed_dict, tokens_in, tokens_out)
        return ({"thought": "sin acciones", "action": None}, 10, 5)


def _accion(nombre: str, args: dict, tok_in: int = 15, tok_out: int = 10) -> tuple[dict, int, int]:
    return ({"thought": f"ejecuto {nombre}", "action": {"name": nombre, "args": args}}, tok_in, tok_out)


def probar_freno_pasos() -> None:
    print("=" * 60)
    print("1. PROBANDO FRENO 1: MÁXIMO DE PASOS")
    print("=" * 60)
    # Se configura un límite estricto de 2 pasos
    guion = [
        _accion("describe_tables", {}),
        _accion("describe_tables", {"db_path": "data/database.sqlite"}),
        _accion("describe_tables", {}),
    ]
    agente = AgenteFrenosGuion(guion, max_steps=2)
    resultado = agente.run("Pregunta que requiere más pasos que el límite configurado")

    print(f"Estado final:   {resultado['status']}")
    print(f"Pasos dados:    {len(resultado['trace'])}")
    print(f"Respuesta dada: {resultado['answer']}")
    print("✓ Freno 1 probado con éxito (traza guardada).\n")


def probar_freno_tokens() -> None:
    print("=" * 60)
    print("2. PROBANDO FRENO 2: PRESUPUESTO DE TOKENS POR CORRIDA")
    print("=" * 60)
    # Presupuesto configurado en 100 tokens. El primer paso consume 120 tokens.
    # Antes del segundo paso, el freno detiene la ejecución.
    guion = [
        _accion("describe_tables", {}, tok_in=80, tok_out=40),  # Total paso 1: 120 tokens
        _accion("execute_query", {"query": "SELECT 1"}, tok_in=50, tok_out=30),
    ]
    agente = AgenteFrenosGuion(guion, max_tokens_budget=100)
    resultado = agente.run("Pregunta intensiva en consumo de contexto")

    print(f"Estado final:   {resultado['status']}")
    print(f"Tokens usados:  {resultado['usage']['tokens_entrada'] + resultado['usage']['tokens_salida']}")
    print(f"Presupuesto:    {agente.max_tokens_budget}")
    print(f"Respuesta dada: {resultado['answer']}")
    print("✓ Freno 2 probado con éxito (traza guardada).\n")


def probar_freno_repeticion() -> None:
    print("=" * 60)
    print("3. PROBANDO FRENO 3: DETECTOR DE REPETICIÓN")
    print("=" * 60)
    # k = 2 repeticiones permitidas. Se envía la misma llamada 3 veces.
    consulta_repetida = "SELECT COUNT(*) FROM ventas"
    guion = [
        _accion("execute_query", {"query": consulta_repetida}),
        _accion("execute_query", {"query": consulta_repetida}),
        _accion("execute_query", {"query": consulta_repetida}),  # 3ra vez -> Dispara freno
    ]
    agente = AgenteFrenosGuion(guion, max_repetitions=2)
    resultado = agente.run("Pregunta que cae en bucle infinito de la misma consulta")

    print(f"Estado final:   {resultado['status']}")
    print(f"Pasos dados:    {len(resultado['trace'])}")
    print(f"Respuesta dada: {resultado['answer']}")
    print("✓ Freno 3 probado con éxito (traza guardada).\n")


if __name__ == "__main__":
    casos = {
        "pasos": probar_freno_pasos,
        "tokens": probar_freno_tokens,
        "repeticion": probar_freno_repeticion,
    }
    if len(sys.argv) > 1 and sys.argv[1] in casos:
        casos[sys.argv[1]]()
    else:
        probar_freno_pasos()
        probar_freno_tokens()
        probar_freno_repeticion()
