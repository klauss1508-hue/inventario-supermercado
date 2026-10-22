-- 07_cobertura_y_riesgo.sql
-- Pregunta: ¿cuántos días de venta cubre el stock actual de cada SKU y cuáles están en riesgo?
-- Demanda diaria = unidades de los últimos 90 días / 90.
-- Riesgo = stock_actual por debajo del stock mínimo vigente.
-- Resultado ordenado de menor a mayor cobertura (los más urgentes primero).

WITH ventas_90d AS (
    SELECT
        sku,
        SUM(unidades) / 90.0 AS demanda_diaria
    FROM ventas
    WHERE fecha >= (SELECT date(MAX(fecha), '-89 days') FROM ventas)
    GROUP BY sku
)
SELECT
    i.sku,
    p.nombre,
    p.categoria,
    p.proveedor,
    i.stock_actual,
    i.stock_minimo_actual,
    ROUND(v.demanda_diaria, 2)                            AS demanda_diaria,
    ROUND(i.stock_actual / v.demanda_diaria, 1)           AS cobertura_dias,
    p.lead_time_dias,
    CASE WHEN i.stock_actual = 0                          THEN 'SIN STOCK'
         WHEN i.stock_actual < i.stock_minimo_actual      THEN 'BAJO MINIMO'
         ELSE 'OK' END                                    AS estado
FROM inventario i
JOIN productos p  ON p.sku = i.sku
JOIN ventas_90d v ON v.sku = i.sku
ORDER BY cobertura_dias ASC;
