-- 05_quiebres_por_proveedor.sql
-- Pregunta: ¿qué proveedores están asociados a más días sin stock?
-- Une stock_diario con productos para agrupar por proveedor.

SELECT
    p.proveedor,
    COUNT(DISTINCT p.sku)                                AS n_sku,
    COUNT(*)                                             AS dias_sku,
    SUM(CASE WHEN s.stock_cierre = 0 THEN 1 ELSE 0 END)  AS dias_en_quiebre,
    ROUND(100.0 * SUM(CASE WHEN s.stock_cierre = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_dias_quiebre,
    ROUND(100.0 - 100.0 * SUM(CASE WHEN s.stock_cierre = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS nivel_servicio_pct
FROM stock_diario s
JOIN productos p ON p.sku = s.sku
GROUP BY p.proveedor
ORDER BY pct_dias_quiebre DESC;
