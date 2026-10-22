-- 03_resumen_abc.sql
-- Pregunta: ¿cuántos SKU hay en cada clase y qué porcentaje de las ventas representan?
-- Repite la clasificación de 02 dentro de un CTE para poder resumirla.

WITH importe_sku AS (
    SELECT sku, SUM(unidades * precio_venta) AS importe
    FROM ventas
    GROUP BY sku
),
acumulado AS (
    SELECT
        sku,
        importe,
        SUM(importe) OVER (ORDER BY importe DESC, sku
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS importe_acum,
        SUM(importe) OVER () AS importe_total
    FROM importe_sku
),
clasificado AS (
    SELECT
        sku,
        importe,
        importe_total,
        CASE
            WHEN 1.0 * importe_acum / importe_total <= 0.80 THEN 'A'
            WHEN 1.0 * importe_acum / importe_total <= 0.95 THEN 'B'
            ELSE 'C'
        END AS clase_abc
    FROM acumulado
)
SELECT
    clase_abc,
    COUNT(*)                                          AS n_sku,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_de_sku,
    ROUND(SUM(importe), 2)                            AS importe_soles,
    ROUND(100.0 * SUM(importe) / MAX(importe_total), 1) AS pct_del_importe
FROM clasificado
GROUP BY clase_abc
ORDER BY clase_abc;
