"""
Generador de datos sintéticos para un supermercado ficticio de Lima (soles, S/).

Simula 24 meses de operación de un centro de distribución (CD) con:
  - Demanda tipo Pareto (pocos SKU concentran la mayoría de las ventas).
  - Variabilidad diaria distinta por producto (necesaria para el stock de seguridad).
  - Estacionalidad mensual por categoría, efecto día de la semana y fechas pico
    (Fiestas Patrias, Navidad / Año Nuevo).
  - Una política de reposición (punto de reorden) deliberadamente imperfecta,
    con lead times reales variables, entregas parciales y quiebres de stock.

Salidas (en --salida, por defecto data/raw):
  productos.csv, ventas.csv, inventario.csv, pedidos_proveedor.csv,
  stock_diario.csv (stock al cierre de cada día por SKU),
  inventario.db (SQLite) y muestra_inventario.xlsx (para el modelo en Excel).

Todo es sintético: no representa datos reales de ninguna empresa.
Uso:  python src/generar_datos.py --seed 42 --n-sku 500
"""

import argparse
import itertools
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

FECHA_INICIO = "2024-10-01"
FECHA_FIN = "2026-09-30"  # 24 meses exactos
FECHA_AJUSTE_PRECIOS = pd.Timestamp("2025-10-01")
AJUSTE_PRECIOS = 1.03  # alza de precios del 3% al inicio del segundo año

# ---------------------------------------------------------------------------
# Catálogo: categoría -> (cantidad de SKU, costo mediano S/, lead time min-max,
#                         {producto base: presentaciones posibles})
# ---------------------------------------------------------------------------
CATALOGO = {
    "Abarrotes": (140, 6.0, (4, 10), {
        "Arroz extra": ["750 g", "1 kg", "5 kg"],
        "Azúcar rubia": ["1 kg", "5 kg"],
        "Fideos spaghetti": ["250 g", "500 g"],
        "Fideos tallarín": ["250 g", "500 g"],
        "Aceite vegetal": ["1 L", "2 L", "5 L"],
        "Harina preparada": ["500 g", "1 kg"],
        "Lentejas": ["500 g", "1 kg"],
        "Frijol canario": ["500 g", "1 kg"],
        "Avena en hojuelas": ["300 g", "500 g"],
        "Atún en conserva": ["140 g", "170 g"],
        "Leche evaporada": ["170 g", "400 g"],
        "Sal de mesa": ["500 g", "1 kg"],
        "Café molido": ["100 g", "200 g"],
        "Galletas de soda": ["6 und", "12 und"],
        "Mermelada de fresa": ["250 g", "500 g"],
        "Salsa de tomate": ["200 g", "400 g"],
        "Mayonesa": ["180 g", "400 g"],
        "Quinua": ["250 g", "500 g"],
        "Chocolate de taza": ["90 g", "180 g"],
        "Sillao": ["150 ml", "500 ml"],
    }),
    "Bebidas": (100, 4.5, (3, 7), {
        "Agua sin gas": ["625 ml", "2.5 L", "7 L"],
        "Gaseosa cola": ["500 ml", "1.5 L", "3 L"],
        "Gaseosa lima-limón": ["500 ml", "1.5 L"],
        "Jugo de frutas": ["300 ml", "1 L"],
        "Néctar de durazno": ["300 ml", "1 L"],
        "Cerveza rubia": ["355 ml", "650 ml"],
        "Bebida rehidratante": ["500 ml", "1 L"],
        "Té helado": ["500 ml", "1.5 L"],
        "Agua con gas": ["625 ml", "1 L"],
        "Chicha morada": ["500 ml", "1 L"],
    }),
    "Lácteos y Refrigerados": (80, 7.0, (2, 4), {
        "Leche fresca": ["946 ml", "1 L"],
        "Yogurt natural": ["1 L", "500 g"],
        "Queso fresco": ["250 g", "500 g"],
        "Mantequilla": ["100 g", "200 g"],
        "Jamón de pavo": ["100 g", "250 g"],
        "Hot dog": ["6 und", "12 und"],
        "Queso edam": ["200 g", "400 g"],
        "Postre de gelatina": ["120 g", "6 und"],
        "Crema de leche": ["200 g", "500 g"],
        "Yogurt de fruta": ["120 g", "1 L"],
    }),
    "Limpieza": (90, 8.0, (5, 12), {
        "Detergente en polvo": ["800 g", "2 kg", "4 kg"],
        "Lejía": ["1 L", "4 L"],
        "Limpiatodo": ["900 ml", "1.8 L"],
        "Lavavajilla": ["500 g", "900 g"],
        "Suavizante de ropa": ["900 ml", "2 L"],
        "Papel higiénico": ["4 rollos", "12 rollos", "24 rollos"],
        "Servilletas": ["100 und", "200 und"],
        "Esponja de cocina": ["2 und", "4 und"],
        "Bolsas de basura": ["10 und", "30 und"],
        "Desinfectante": ["650 ml", "1.8 L"],
    }),
    "Cuidado Personal": (90, 10.0, (5, 12), {
        "Shampoo": ["200 ml", "400 ml", "750 ml"],
        "Acondicionador": ["200 ml", "400 ml"],
        "Jabón de tocador": ["90 g", "3 und"],
        "Pasta dental": ["75 ml", "100 ml"],
        "Desodorante": ["50 ml", "150 ml"],
        "Crema corporal": ["200 ml", "400 ml"],
        "Toallas higiénicas": ["8 und", "16 und"],
        "Pañales": ["30 und", "60 und"],
        "Cepillo dental": ["1 und", "2 und"],
        "Afeitadora desechable": ["2 und", "4 und"],
    }),
}

# Marcas ficticias (no representan marcas reales)
MARCAS = ["Valle Dorado", "Pampa Real", "Brisa Andina", "Nevado", "Sol Naciente",
          "Costa Verde", "Mar Azul", "Tierra Fértil", "Campo Fresco", "Casa Limpia"]

# Estacionalidad mensual (enero a diciembre) por categoría
ESTACIONALIDAD_BASE = [0.95, 0.92, 0.98, 0.97, 1.00, 1.00, 1.08, 1.00, 0.98, 1.00, 1.08, 1.30]
ESTACIONALIDAD = {
    "Abarrotes": ESTACIONALIDAD_BASE,
    "Bebidas": [1.25, 1.25, 1.15, 0.95, 0.85, 0.80, 0.90, 0.85, 0.95, 1.05, 1.10, 1.30],  # verano limeño
    "Lácteos y Refrigerados": ESTACIONALIDAD_BASE,
    "Limpieza": [1.10, 1.10, 1.05, 1.00, 0.98, 0.95, 1.00, 0.95, 0.95, 1.00, 1.05, 1.20],
    "Cuidado Personal": [0.95, 0.92, 0.98, 0.97, 1.15, 1.00, 1.05, 1.00, 0.98, 1.00, 1.08, 1.20],
}
# Efecto día de la semana (lunes a domingo)
FACTOR_DIA_SEMANA = [0.90, 0.90, 0.90, 0.95, 1.10, 1.25, 1.15]


def factor_diario(fechas: pd.DatetimeIndex, categoria: str) -> np.ndarray:
    """Multiplicador de demanda por día: mes x día de la semana x eventos x tendencia."""
    mes = np.array(ESTACIONALIDAD[categoria])[fechas.month - 1]
    dow = np.array(FACTOR_DIA_SEMANA)[fechas.dayofweek]
    evento = np.ones(len(fechas))
    # Fiestas Patrias (26 a 29 de julio)
    evento[(fechas.month == 7) & (fechas.day >= 26) & (fechas.day <= 29)] *= 1.20
    # Navidad (20 a 24 de diciembre) y Año Nuevo (28 a 31 de diciembre)
    evento[(fechas.month == 12) & (fechas.day >= 20) & (fechas.day <= 24)] *= 1.35
    evento[(fechas.month == 12) & (fechas.day >= 28)] *= 1.25
    # Tendencia de crecimiento: 0.4% mensual
    meses = (fechas.year - fechas[0].year) * 12 + (fechas.month - fechas[0].month)
    tendencia = 1 + 0.004 * np.asarray(meses)
    return mes * dow * evento * tendencia


def generar_productos(rng: np.random.Generator, n_sku: int) -> pd.DataFrame:
    """Catálogo de productos con costo, precio, lead time planificado y proveedor."""
    total_base = sum(v[0] for v in CATALOGO.values())
    filas = []
    for categoria, (n_base, costo_med, (lt_min, lt_max), items) in CATALOGO.items():
        n_cat = max(1, round(n_base * n_sku / total_base))
        combos = [(i, p, m) for i, pres in items.items() for p in pres for m in MARCAS]
        elegidos = rng.choice(len(combos), size=n_cat, replace=False)
        for idx in elegidos:
            item, pres, marca = combos[idx]
            costo = float(np.round(costo_med * rng.lognormal(0, 0.55), 2))
            costo = max(costo, 0.6)
            margen = rng.uniform(0.12, 0.35)
            precio = float(np.round(costo * (1 + margen), 1))  # precios a 10 céntimos
            precio = max(precio, round(costo + 0.1, 1))
            filas.append({
                "categoria": categoria,
                "nombre": f"{item} {pres} - {marca}",
                "costo_unitario": costo,
                "precio_venta": precio,
                "lead_time_dias": int(rng.integers(lt_min, lt_max + 1)),
                "proveedor": f"Proveedor {int(rng.integers(1, 13)):02d}",
            })
    df = pd.DataFrame(filas).sample(frac=1, random_state=int(rng.integers(0, 10_000))).reset_index(drop=True)
    df.insert(0, "sku", [f"SKU{i + 1:04d}" for i in range(len(df))])
    return df


def asignar_demanda_base(rng: np.random.Generator, productos: pd.DataFrame) -> np.ndarray:
    """Demanda diaria media por SKU con forma Pareto; los productos baratos rotan algo más."""
    n = len(productos)
    z_costo = (np.log(productos["costo_unitario"]) - np.log(productos["costo_unitario"]).mean())
    puntaje = rng.normal(0, 1, n) - 0.5 * z_costo.to_numpy()
    rango = np.empty(n, dtype=int)
    rango[np.argsort(-puntaje)] = np.arange(1, n + 1)  # rango 1 = producto estrella
    alfa, lam_max = 1.15, 200.0
    return lam_max * rango.astype(float) ** (-alfa)


def simular_sku(rng, fechas, demanda_potencial, lead_time_plan, lam_base, k_disp):
    """
    Simula inventario y reposición de un SKU con una política de punto de reorden (ROP).
    Devuelve ventas diarias realizadas, pedidos al proveedor, el stock al cierre de
    cada día, y el stock/ROP finales.
    """
    n_dias = len(fechas)
    # Política que aplica el supermercado (imperfecta a propósito: z = 1.0 y sd subestimada)
    sd_diaria = np.sqrt(lam_base + lam_base ** 2 / k_disp)
    rop = int(np.ceil(lam_base * lead_time_plan + 1.0 * sd_diaria * np.sqrt(lead_time_plan)))
    dias_cobertura = int(rng.integers(10, 22))
    q = max(int(np.ceil(lam_base * dias_cobertura)), 6)

    stock = rop + q
    pendientes = []  # (dia_llegada, cantidad)
    ventas = np.zeros(n_dias, dtype=int)
    stock_dia = np.zeros(n_dias, dtype=int)  # stock al cierre de cada día
    pedidos = []

    for t in range(n_dias):
        # 1) Llegan pedidos
        llegan = [p for p in pendientes if p[0] <= t]
        if llegan:
            stock += sum(p[1] for p in llegan)
            pendientes = [p for p in pendientes if p[0] > t]
        # 2) Venta realizada (si no hay stock, se pierde la venta)
        vendido = min(int(demanda_potencial[t]), stock)
        ventas[t] = vendido
        stock -= vendido
        stock_dia[t] = stock
        # 3) Revisión diaria: se pide si la posición de inventario cae bajo el ROP
        posicion = stock + sum(p[1] for p in pendientes)
        if posicion <= rop and not pendientes:
            r = rng.random()
            retraso = 0 if r < 0.70 else 1 if r < 0.85 else 2 if r < 0.93 else int(rng.integers(3, 6))
            if rng.random() < 0.05:
                retraso = -1  # entrega adelantada
            lt_real = max(1, lead_time_plan + retraso)
            llegada = t + lt_real
            if rng.random() < 0.08:  # entrega parcial (afecta OTIF)
                cant_recibida = max(1, int(q * rng.uniform(0.6, 0.9)))
            else:
                cant_recibida = q
            pendientes.append((llegada, cant_recibida))
            if llegada < n_dias:
                pedidos.append({
                    "fecha_pedido": fechas[t],
                    "fecha_entrega_prometida": fechas[t] + pd.Timedelta(days=lead_time_plan),
                    "fecha_recepcion": fechas[llegada],
                    "cantidad_pedida": q,
                    "cantidad_recibida": cant_recibida,
                })
    return ventas, pedidos, stock_dia, stock, rop


def generar(seed: int, n_sku: int, salida: Path) -> None:
    rng = np.random.default_rng(seed)
    fechas = pd.date_range(FECHA_INICIO, FECHA_FIN, freq="D")

    productos = generar_productos(rng, n_sku)
    lam_base = asignar_demanda_base(rng, productos)
    k_disp = rng.uniform(3, 25, len(productos))  # menor k = demanda más volátil

    bloques_ventas, bloques_stock, filas_pedidos, filas_inv = [], [], [], []
    for i, prod in productos.iterrows():
        fac = factor_diario(fechas, prod["categoria"])
        mu = lam_base[i] * fac
        p = k_disp[i] / (k_disp[i] + mu)
        demanda = rng.negative_binomial(k_disp[i], p)

        ventas, pedidos, stock_dia, stock_fin, rop = simular_sku(
            rng, fechas, demanda, int(prod["lead_time_dias"]), lam_base[i], k_disp[i])

        bloques_stock.append(pd.DataFrame({
            "fecha": fechas, "sku": prod["sku"], "stock_cierre": stock_dia}))

        dias = np.nonzero(ventas)[0]
        precio_nuevo = prod["precio_venta"]
        precio_antes = np.round(precio_nuevo / AJUSTE_PRECIOS, 2)
        precios = np.where(fechas[dias] >= FECHA_AJUSTE_PRECIOS, precio_nuevo, precio_antes)
        bloques_ventas.append(pd.DataFrame({
            "fecha": fechas[dias], "sku": prod["sku"],
            "unidades": ventas[dias], "precio_venta": precios}))
        for ped in pedidos:
            ped["sku"] = prod["sku"]
            filas_pedidos.append(ped)
        filas_inv.append({"sku": prod["sku"], "stock_actual": int(stock_fin),
                          "stock_minimo_actual": int(rop)})

    ventas = pd.concat(bloques_ventas, ignore_index=True).sort_values(["fecha", "sku"]).reset_index(drop=True)
    pedidos = pd.DataFrame(filas_pedidos).sort_values(["fecha_pedido", "sku"]).reset_index(drop=True)
    pedidos.insert(0, "id_pedido", [f"PO{i + 1:06d}" for i in range(len(pedidos))])
    pedidos["lead_time_real_dias"] = (pedidos["fecha_recepcion"] - pedidos["fecha_pedido"]).dt.days
    pedidos = pedidos[["id_pedido", "sku", "fecha_pedido", "fecha_entrega_prometida", "fecha_recepcion",
                       "cantidad_pedida", "cantidad_recibida", "lead_time_real_dias"]]
    inventario = pd.DataFrame(filas_inv)
    stock_diario = pd.concat(bloques_stock, ignore_index=True).sort_values(["fecha", "sku"]).reset_index(drop=True)

    # --- Exportar -----------------------------------------------------------
    salida.mkdir(parents=True, exist_ok=True)
    productos.to_csv(salida / "productos.csv", index=False)
    ventas.to_csv(salida / "ventas.csv", index=False, date_format="%Y-%m-%d")
    inventario.to_csv(salida / "inventario.csv", index=False)
    stock_diario.to_csv(salida / "stock_diario.csv", index=False, date_format="%Y-%m-%d")
    pedidos.to_csv(salida / "pedidos_proveedor.csv", index=False, date_format="%Y-%m-%d")

    # SQLite
    ruta_db = salida / "inventario.db"
    if ruta_db.exists():
        ruta_db.unlink()
    with sqlite3.connect(ruta_db) as con:
        for nombre, df in [("productos", productos), ("ventas", ventas),
                           ("inventario", inventario), ("pedidos_proveedor", pedidos),
                           ("stock_diario", stock_diario)]:
            d = df.copy()
            for c in d.select_dtypes("datetime").columns:
                d[c] = d[c].dt.strftime("%Y-%m-%d")
            d.to_sql(nombre, con, index=False)
        con.execute("CREATE INDEX idx_ventas_sku ON ventas(sku)")
        con.execute("CREATE INDEX idx_ventas_fecha ON ventas(fecha)")
        con.execute("CREATE INDEX idx_pedidos_sku ON pedidos_proveedor(sku)")
        con.execute("CREATE INDEX idx_stock_sku ON stock_diario(sku)")
        con.execute("CREATE INDEX idx_stock_fecha ON stock_diario(fecha)")

    # Excel: ventas agregadas por mes (las ventas diarias son muy pesadas para Excel)
    ventas_mes = (ventas.assign(mes=ventas["fecha"].dt.to_period("M").astype(str),
                                importe=ventas["unidades"] * ventas["precio_venta"])
                  .groupby(["sku", "mes"], as_index=False)
                  .agg(unidades=("unidades", "sum"), importe=("importe", "sum")))
    ventas_mes["importe"] = ventas_mes["importe"].round(2)
    # Stock mensual: promedio de stock al cierre y días en quiebre (stock = 0) por SKU y mes
    stock_mes = (stock_diario.assign(mes=stock_diario["fecha"].dt.to_period("M").astype(str),
                                     quiebre=(stock_diario["stock_cierre"] == 0).astype(int))
                 .groupby(["sku", "mes"], as_index=False)
                 .agg(stock_promedio=("stock_cierre", "mean"), dias_quiebre=("quiebre", "sum")))
    stock_mes["stock_promedio"] = stock_mes["stock_promedio"].round(1)
    with pd.ExcelWriter(salida / "muestra_inventario.xlsx", engine="openpyxl") as xw:
        productos.to_excel(xw, sheet_name="productos", index=False)
        inventario.to_excel(xw, sheet_name="inventario", index=False)
        ventas_mes.to_excel(xw, sheet_name="ventas_mensuales", index=False)
        stock_mes.to_excel(xw, sheet_name="stock_mensual", index=False)

    print(f"SKU: {len(productos)} | ventas: {len(ventas):,} filas | pedidos: {len(pedidos):,} filas "
          f"| stock_diario: {len(stock_diario):,} filas")
    print(f"Periodo: {fechas[0].date()} a {fechas[-1].date()} | archivos en: {salida}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Genera datos sintéticos de inventario de supermercado.")
    ap.add_argument("--seed", type=int, default=42, help="semilla aleatoria (reproducibilidad)")
    ap.add_argument("--n-sku", type=int, default=500, help="cantidad de SKU")
    ap.add_argument("--salida", type=Path, default=Path("data/raw"), help="carpeta de salida")
    args = ap.parse_args()
    generar(args.seed, args.n_sku, args.salida)
