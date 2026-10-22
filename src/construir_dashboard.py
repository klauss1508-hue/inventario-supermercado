"""
Construye dashboard/index.html a partir de la base SQLite.

Calcula los KPIs con la misma lógica que el notebook (notebooks/01_analisis_reposicion.ipynb)
y los inserta como JSON en dashboard/plantilla.html. Así el tablero no tiene cifras escritas
a mano: si cambian los datos, basta con volver a ejecutar este script.

Uso:  python src/construir_dashboard.py
"""

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "data" / "raw" / "inventario.db"
PLANTILLA = RAIZ / "dashboard" / "plantilla.html"
SALIDA = RAIZ / "dashboard" / "index.html"

Z = 1.65
INICIO_12M = pd.Timestamp("2025-10-01")


def cargar():
    with sqlite3.connect(DB) as con:
        productos = pd.read_sql("SELECT * FROM productos", con)
        ventas = pd.read_sql("SELECT * FROM ventas", con, parse_dates=["fecha"])
        inventario = pd.read_sql("SELECT * FROM inventario", con)
        pedidos = pd.read_sql("SELECT * FROM pedidos_proveedor", con,
                              parse_dates=["fecha_pedido", "fecha_entrega_prometida", "fecha_recepcion"])
        stock = pd.read_sql("SELECT * FROM stock_diario", con, parse_dates=["fecha"])
    return productos, ventas, inventario, pedidos, stock


def clasificar_abc(ventas):
    importe = (ventas.assign(importe=ventas["unidades"] * ventas["precio_venta"])
                     .groupby("sku")["importe"].sum().sort_values(ascending=False))
    abc = importe.to_frame()
    abc["pct_acumulado"] = abc["importe"].cumsum() / abc["importe"].sum()
    abc["clase_abc"] = np.select([abc["pct_acumulado"] <= 0.80, abc["pct_acumulado"] <= 0.95], ["A", "B"], "C")
    return abc


def rop(d, sd, lt, z, sd_lt=0):
    """Stock de seguridad y ROP redondeados hacia arriba (igual que en el notebook)."""
    ss = np.ceil(z * np.sqrt(lt * sd ** 2 + d ** 2 * sd_lt ** 2))
    return ss, np.ceil(d * lt + ss)


def main():
    productos, ventas, inventario, pedidos, stock = cargar()
    abc = clasificar_abc(ventas)

    # Demanda diaria del último año: calendario completo, sin los días en quiebre
    diario = (stock[stock["fecha"] >= INICIO_12M]
              .merge(ventas[["fecha", "sku", "unidades"]], on=["fecha", "sku"], how="left")
              .fillna({"unidades": 0}))
    demanda = diario[diario["stock_cierre"] > 0].groupby("sku")["unidades"].agg(d_media="mean", d_sd="std")
    lead_time = pedidos.groupby("sku")["lead_time_real_dias"].agg(lt_media="mean", lt_sd="std")
    quiebre = (stock["stock_cierre"] == 0).groupby(stock["sku"]).mean().rename("pct_dias_quiebre") * 100

    repo = (productos.merge(inventario, on="sku").merge(demanda, on="sku").merge(lead_time, on="sku")
                     .merge(abc["clase_abc"], left_on="sku", right_index=True).merge(quiebre, on="sku"))
    repo["stock_seguridad"], repo["rop_recomendado"] = rop(repo["d_media"], repo["d_sd"], repo["lt_media"], Z,
                                                           repo["lt_sd"])
    repo["brecha"] = repo["rop_recomendado"] - repo["stock_minimo_actual"]
    repo["inversion"] = repo["brecha"].clip(lower=0) * repo["costo_unitario"]
    repo["capital"] = repo["stock_actual"] * repo["costo_unitario"]

    # Nivel de servicio por ciclo: pedidos sin stock 0 mientras se esperaba la entrega
    dias_cero = stock.loc[stock["stock_cierre"] == 0, ["sku", "fecha"]]
    cruce = pedidos[["id_pedido", "sku", "fecha_pedido", "fecha_recepcion"]].merge(dias_cero, on="sku")
    en_espera = (cruce["fecha"] > cruce["fecha_pedido"]) & (cruce["fecha"] < cruce["fecha_recepcion"])
    pedidos["ciclo_ok"] = ~pedidos["id_pedido"].isin(cruce.loc[en_espera, "id_pedido"])
    pedidos["otif"] = ((pedidos["fecha_recepcion"] <= pedidos["fecha_entrega_prometida"])
                       & (pedidos["cantidad_recibida"] >= pedidos["cantidad_pedida"]))
    pedidos = pedidos.merge(productos[["sku", "categoria"]], on="sku")

    # Puente del ROP: se agrega un factor a la vez
    r = repo
    pasos = [
        ("ROP actual", r["stock_minimo_actual"].sum()),
        ("Demanda real", rop(r["d_media"], r["d_sd"], r["lead_time_dias"], 1.0)[1].sum()),
        ("z = 1.65", rop(r["d_media"], r["d_sd"], r["lead_time_dias"], Z)[1].sum()),
        ("Lead time real", rop(r["d_media"], r["d_sd"], r["lt_media"], Z)[1].sum()),
        ("Variabilidad del lead time", r["rop_recomendado"].sum()),
    ]

    por_categoria = (repo.groupby("categoria")
                         .agg(n_sku=("sku", "size"), inversion=("inversion", "sum"),
                              rop_actual=("stock_minimo_actual", "sum"), rop_rec=("rop_recomendado", "sum"),
                              quiebre=("pct_dias_quiebre", "mean"))
                         .join(pedidos.groupby("categoria")["ciclo_ok"].mean().mul(100).rename("servicio_ciclo"))
                         .reset_index())
    por_clase = (repo.groupby("clase_abc")
                     .agg(n_sku=("sku", "size"), inversion=("inversion", "sum"), capital=("capital", "sum"),
                          rop_actual=("stock_minimo_actual", "sum"), rop_rec=("rop_recomendado", "sum"),
                          quiebre=("pct_dias_quiebre", "mean"))
                     .join(abc.groupby("clase_abc")["importe"].sum().rename("importe"))
                     .reset_index())

    datos = {
        "kpi": {
            "n_sku": len(repo),
            "sku_clase_a": int((abc["clase_abc"] == "A").sum()),
            "pct_importe_a": abc.loc[abc["clase_abc"] == "A", "importe"].sum() / abc["importe"].sum() * 100,
            "servicio_ciclo": pedidos["ciclo_ok"].mean() * 100,
            "sku_bajo_minimo": int((inventario["stock_actual"] < inventario["stock_minimo_actual"]).sum()),
            "sku_en_cero": int((inventario["stock_actual"] == 0).sum()),
            "capital": repo["capital"].sum(),
            "pct_capital_a": repo.loc[repo["clase_abc"] == "A", "capital"].sum() / repo["capital"].sum() * 100,
            "otif": pedidos["otif"].mean() * 100,
            "n_pedidos": len(pedidos),
            "sku_rop_insuficiente": int((repo["brecha"] > 0).sum()),
            "inversion": repo["inversion"].sum(),
        },
        "pareto": [round(v * 100, 2) for v in abc["pct_acumulado"]],
        "puente": [{"paso": p, "total": int(v)} for p, v in pasos],
        "categorias": por_categoria.round(2).to_dict("records"),
        "clases": por_clase.round(2).to_dict("records"),
        "skus": (repo.sort_values("inversion", ascending=False)
                     [["sku", "nombre", "categoria", "clase_abc", "stock_actual", "stock_minimo_actual",
                       "rop_recomendado", "brecha", "inversion", "pct_dias_quiebre"]]
                     .rename(columns={"stock_minimo_actual": "rop_actual", "pct_dias_quiebre": "quiebre"})
                     .round(2).to_dict("records")),
    }
    datos["kpi"] = {k: round(float(v), 2) for k, v in datos["kpi"].items()}

    html = PLANTILLA.read_text(encoding="utf-8")
    html = html.replace("/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    SALIDA.write_text(html, encoding="utf-8")
    print(f"Dashboard generado: {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
