-- 09_margen_por_categoria.sql
-- Pregunta: ¿qué categorías dejan más margen bruto y cuál es su margen porcentual?
-- Tablas: ventas, productos
-- Nota: el margen usa el costo unitario actual de `productos` (simplificación).

SELECT
    p.categoria,
    COUNT(DISTINCT p.sku)                                   AS n_sku,
    ROUND(SUM(v.unidades * v.precio_venta), 2)              AS importe_soles,
    ROUND(SUM(v.unidades * (v.precio_venta - p.costo_unitario)), 2) AS margen_bruto_soles,
    ROUND(100.0 * SUM(v.unidades * (v.precio_venta - p.costo_unitario))
          / SUM(v.unidades * v.precio_venta), 1)            AS margen_pct,
    ROUND(100.0 * SUM(v.unidades * (v.precio_venta - p.costo_unitario))
          / SUM(SUM(v.unidades * (v.precio_venta - p.costo_unitario))) OVER (), 1) AS pct_del_margen_total
FROM ventas v
JOIN productos p ON p.sku = v.sku
GROUP BY p.categoria
ORDER BY margen_bruto_soles DESC;
