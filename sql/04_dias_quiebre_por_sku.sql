-- 04_dias_quiebre_por_sku.sql
-- Pregunta: ¿qué productos pasan más días sin stock?
-- Definición: un día en quiebre es un día con stock_cierre = 0.
-- Nota: no hay registro de la demanda perdida, así que esto mide disponibilidad, no ventas perdidas.

SELECT
    s.sku,
    p.nombre,
    p.categoria,
    p.proveedor,
    COUNT(*)                                             AS dias_totales,
    SUM(CASE WHEN s.stock_cierre = 0 THEN 1 ELSE 0 END)  AS dias_en_quiebre,
    ROUND(100.0 * SUM(CASE WHEN s.stock_cierre = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_dias_quiebre,
    ROUND(100.0 - 100.0 * SUM(CASE WHEN s.stock_cierre = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS nivel_servicio_pct
FROM stock_diario s
JOIN productos p ON p.sku = s.sku
GROUP BY s.sku, p.nombre, p.categoria, p.proveedor
ORDER BY dias_en_quiebre DESC, s.sku;
