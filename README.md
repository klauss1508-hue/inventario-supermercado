# Clasificación ABC y política de reposición de inventario

Proyecto de portafolio (en construcción) sobre un supermercado **ficticio** de Lima: ¿qué productos concentran el 80% de las ventas y cuánto stock de seguridad y punto de reorden necesita cada uno?

> Los datos son **sintéticos**, generados con `src/generar_datos.py`. Las marcas y los proveedores son inventados.

## Cómo ejecutarlo

Requisitos: Python 3.10 o superior.

```bash
git clone https://github.com/<tu-usuario>/inventario-supermercado.git
cd inventario-supermercado
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Regenera los CSV, el Excel y la base SQLite inventario.db en data/raw/
python src/generar_datos.py --seed 42 --n-sku 500
```

La misma semilla produce siempre los mismos datos. `inventario.db` no se sube al repositorio porque pesa unos 35 MB; el script la vuelve a crear.

Las consultas de `sql/` (dialecto SQLite) se ejecutan contra `data/raw/inventario.db`, por ejemplo desde [DB Browser for SQLite](https://sqlitebrowser.org/) o con:

```bash
sqlite3 data/raw/inventario.db < sql/02_clasificacion_abc.sql
```

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/` | Generador de datos sintéticos |
| `data/raw/` | CSV de productos, ventas, inventario, pedidos a proveedor y stock diario, más una muestra en Excel |
| `sql/` | 8 consultas numeradas: ABC, quiebres, OTIF, cobertura y capital inmovilizado |
