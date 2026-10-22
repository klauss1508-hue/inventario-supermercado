-- 08_capital_inmovilizado_por_abc.sql
-- Pregunta: ¿cuánto dinero hay parado en inventario y en qué clase ABC está?
-- Capital inmovilizado = stock_actual * costo_unitario.
-- Un capital alto en clase C con poca venta es una señal de sobrestock.

WITH importe_sku AS (
    SELECT sku, SUM(unidades * precio_venta) AS importe
    FROM ventas
    GROUP BY sku
),
acumulado AS (
    SELECT
        sku,
        SUM(importe) OVER (ORDER BY importe DESC, sku
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS importe_acum,
        SUM(importe) OVER () AS importe_total
    FROM importe_sku
),
clasificado AS (
    SELECT
        sku,
        CASE
            WHEN 1.0 * importe_acum / importe_total <= 0.80 THEN 'A'
            WHEN 1.0 * importe_acum / importe_total <= 0.95 THEN 'B'
            ELSE 'C'
        END AS clase_abc
    FROM acumulado
)
SELECT
    c.clase_abc,
    COUNT(*)                                              AS n_sku,
    SUM(i.stock_actual)                                   AS unidades_en_stock,
    ROUND(SUM(i.stock_actual * p.costo_unitario), 2)      AS capital_inmovilizado_soles,
    ROUND(100.0 * SUM(i.stock_actual * p.costo_unitario)
          / SUM(SUM(i.stock_actual * p.costo_unitario)) OVER (), 1) AS pct_del_capital
FROM inventario i
JOIN productos p   ON p.sku = i.sku
JOIN clasificado c ON c.sku = i.sku
GROUP BY c.clase_abc
ORDER BY c.clase_abc;
