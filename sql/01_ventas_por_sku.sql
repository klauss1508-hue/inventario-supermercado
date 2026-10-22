-- 01_ventas_por_sku.sql
-- Pregunta: ¿cuánto vendió cada producto en los 24 meses y cuánto margen dejó?
-- Tablas: ventas, productos
-- Nota: el margen usa el costo unitario actual de `productos` (simplificación).

SELECT
    p.sku,
    p.nombre,
    p.categoria,
    SUM(v.unidades)                                         AS unidades,
    ROUND(SUM(v.unidades * v.precio_venta), 2)              AS importe_soles,
    ROUND(SUM(v.unidades * (v.precio_venta - p.costo_unitario)), 2) AS margen_bruto_soles,
    ROUND(100.0 * SUM(v.unidades * (v.precio_venta - p.costo_unitario))
          / SUM(v.unidades * v.precio_venta), 1)            AS margen_pct
FROM ventas v
JOIN productos p ON p.sku = v.sku
GROUP BY p.sku, p.nombre, p.categoria
ORDER BY importe_soles DESC;
