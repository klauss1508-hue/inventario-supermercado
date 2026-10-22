-- 06_otif_por_proveedor.sql
-- Pregunta: ¿qué proveedores cumplen a tiempo y completo (OTIF)?
-- A tiempo   = fecha_recepcion <= fecha_entrega_prometida
-- Completo   = cantidad_recibida >= cantidad_pedida
-- OTIF       = ambas condiciones a la vez
-- Las fechas están guardadas como texto AAAA-MM-DD, por eso se comparan directamente.

SELECT
    p.proveedor,
    COUNT(*)                                                       AS pedidos,
    ROUND(100.0 * AVG(po.fecha_recepcion <= po.fecha_entrega_prometida), 1) AS pct_a_tiempo,
    ROUND(100.0 * AVG(po.cantidad_recibida >= po.cantidad_pedida), 1)       AS pct_completo,
    ROUND(100.0 * AVG(po.fecha_recepcion <= po.fecha_entrega_prometida
                      AND po.cantidad_recibida >= po.cantidad_pedida), 1)   AS pct_otif,
    ROUND(AVG(p.lead_time_dias), 2)                                AS lead_time_plan_prom,
    ROUND(AVG(po.lead_time_real_dias), 2)                          AS lead_time_real_prom
FROM pedidos_proveedor po
JOIN productos p ON p.sku = po.sku
GROUP BY p.proveedor
ORDER BY pct_otif ASC;
