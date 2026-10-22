-- 10_rotacion_por_categoria.sql
-- Pregunta: ¿cuántas veces al año se renueva el inventario de cada categoría?
-- Rotación anual = costo de lo vendido en los últimos 12 meses / inventario promedio a costo.
-- Inventario promedio = promedio del stock al cierre de cada día (stock_diario), no la foto final.
-- Días de inventario = 365 / rotación (cuántos días de venta hay en el almacén, en promedio).

WITH costo_vendido AS (
    SELECT
        v.sku,
        SUM(v.unidades * p.costo_unitario) AS costo_ventas
    FROM ventas v
    JOIN productos p ON p.sku = v.sku
    WHERE v.fecha >= (SELECT date(MAX(fecha), '-364 days') FROM ventas)
    GROUP BY v.sku
),
stock_promedio AS (
    SELECT
        s.sku,
        AVG(s.stock_cierre * p.costo_unitario) AS inventario_prom
    FROM stock_diario s
    JOIN productos p ON p.sku = s.sku
    WHERE s.fecha >= (SELECT date(MAX(fecha), '-364 days') FROM stock_diario)
    GROUP BY s.sku
)
SELECT
    p.categoria,
    COUNT(*)                                                AS n_sku,
    ROUND(SUM(c.costo_ventas), 2)                           AS costo_ventas_12m_soles,
    ROUND(SUM(s.inventario_prom), 2)                        AS inventario_prom_soles,
    ROUND(SUM(c.costo_ventas) / SUM(s.inventario_prom), 1)  AS rotacion_anual,
    ROUND(365.0 * SUM(s.inventario_prom) / SUM(c.costo_ventas), 1) AS dias_inventario
FROM productos p
JOIN costo_vendido c  ON c.sku = p.sku
JOIN stock_promedio s ON s.sku = p.sku
GROUP BY p.categoria
ORDER BY rotacion_anual DESC;
