-- 02_clasificacion_abc.sql
-- Pregunta: ¿qué productos concentran las ventas? (análisis de Pareto / ABC)
-- Regla: A = hasta 80% del importe acumulado, B = hasta 95%, C = el resto.
-- Técnica: función de ventana SUM() OVER con orden descendente por importe.

WITH importe_sku AS (
    SELECT
        sku,
        SUM(unidades * precio_venta) AS importe
    FROM ventas
    GROUP BY sku
),
acumulado AS (
    SELECT
        sku,
        importe,
        SUM(importe) OVER (ORDER BY importe DESC, sku
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS importe_acum,
        SUM(importe) OVER ()                                                   AS importe_total,
        ROW_NUMBER() OVER (ORDER BY importe DESC, sku)                         AS ranking
    FROM importe_sku
)
SELECT
    a.ranking,
    a.sku,
    p.nombre,
    p.categoria,
    ROUND(a.importe, 2)                              AS importe_soles,
    ROUND(100.0 * a.importe / a.importe_total, 2)    AS pct_del_total,
    ROUND(100.0 * a.importe_acum / a.importe_total, 2) AS pct_acumulado,
    CASE
        WHEN 1.0 * a.importe_acum / a.importe_total <= 0.80 THEN 'A'
        WHEN 1.0 * a.importe_acum / a.importe_total <= 0.95 THEN 'B'
        ELSE 'C'
    END                                              AS clase_abc
FROM acumulado a
JOIN productos p ON p.sku = a.sku
ORDER BY a.ranking;
