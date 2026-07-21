# ISC data harmonization (script 04)

This script transforms Rijkswaterstaat (RWS) ISC export data into the Dutch output format required by the Internationale Scheldecommissie (ISC).

For exploratory duplicate and aquocode analysis, see `03_Exploring_duplicates.ipynb`.

## Prerequisites

- Python 3.10+
- pandas
- openpyxl (for reading `.xlsx` files)

Install dependencies:

```bash
pip install pandas openpyxl
```

## How to run

### Option A: Jupyter notebook (recommended for inspection)

1. Open `scripts/04_harmonize_isc_data.ipynb` in Jupyter or VS Code.
2. Set `TARGET_YEAR` in the configuration cell (default: 2024).
3. Run all cells from top to bottom.
4. Output is written to:
   `voorbeeld/isc_2023-2025/ISC_{YEAR}_harmonized.csv`
   `voorbeeld/isc_2023-2025/ISC_{YEAR}_harmonized.xlsx`

From the repository root:

```bash
jupyter notebook scripts/04_harmonize_isc_data.ipynb
```

### Option B: Python module (reproducible run)

From the repository root:

```bash
python -c "from scripts.isc_harmonization import run_harmonization_pipeline; run_harmonization_pipeline(2024)"
```

Or from the `scripts` folder:

```bash
python -c "from isc_harmonization import run_harmonization_pipeline; run_harmonization_pipeline(2024)"
```

## Required input files

| File | Purpose |
|------|---------|
| `voorbeeld/isc_2023-2025/ISC_{YEAR}.xlsx` | Raw ISC measurement export for the target year |
| `mappings/locations-mapped.xlsx` | RWS location code → ISC station ID |
| `mappings/parameter_mapping_final.xlsx` (sheet: `mapping`) | Parameter combination → ISC parameter ID, unit, and conversion |
| `mappings/hoedanigheid_mapped.xlsx` | Fraction code → ISC fraction label |
| `voorbeeld/isc_2023-2025/SCHAARVODDL + SASVGT_CHLfa_2023-2025.xlsx` | Chlorophyll-a measurements (separate RWS format) |

All paths are resolved relative to the repository root.

## Column naming

The pipeline uses **Dutch ISC output column names from the start**. Mapping tables and raw RWS data keep their original source column names (e.g. `locatie_code`, `parameter_code`, `eventdatum`). French column names from mapping tables are converted to Dutch when merged:

| Mapping table column | Dutch column used in pipeline |
|----------------------|-------------------------------|
| `Identitication unique de la station` | `Unieke identiticatie meetpunt` |
| `ISC_fraction` | `Geanalyseerde fractie` |

## Processing steps

### 1. Load data and mappings

Raw measurements and three mapping tables are loaded. Parameters marked `reported = N` in the mapping are kept aside as **not measured (NM)**. Parameters marked `S` are excluded from the measured set.

### 2. Map parameters

Each row is matched on:

- `parameter_code`
- `grootheid_code`
- `hoedanigheid_code`
- `eenheid_code`

Rows without a match are dropped. ISC parameter ID and unit are added using Dutch column names.

### 3. Map location and fraction

- **Location:** `locatie_code` → `Unieke identiticatie meetpunt`
- **Fraction:** `hoedanigheid_code` → `Geanalyseerde fractie`

### 4. Filter measurements

Rows are kept only when:

- `waardebewerkings_methode_code` ≠ `BER`
- `bemonsteringshoogte_code` == `-100`
- `event_aquocode` in `[0, 3, 90, 99]`

### 5. Resolve duplicate aquocodes

For identical station + date + fraction + parameter + unit, only the row with the **lowest** valid aquocode is kept.

### 6. Build harmonized output

- Sort by station, date, parameter
- Format date as `Datum staalname` (`dd/mm/YYYY`)
- Compute `Resultaat`: `event_waarde × conversion`
- Set `Aanpak kwantificeringsgrens` to `=` when value is numeric and symbol is missing

### 7. Aggregate compound parameters

Some ISC parameters are sums of other parameters:

| Target ID | Source IDs | Remove sources? |
|-----------|------------|-----------------|
| 1774 | 1283, 1629, 1630 | No |
| 5534 | 1103, 1181, 1173, 1207 | No |
| 6561 | 6561a, 6561b | Yes |

Incomplete groups or conflicting LQ symbols are logged as warnings during execution.

### 8. Format and select output

- Sort by station, parameter, date
- Format numeric `Resultaat` values to 4 decimal places (as text)
- Set `Resultaat` to `NV` when aquocode is 99
- Keep the 7 Dutch output columns

### 9. Append chlorophyll-a

Chlorophyll data from SCHAARVODDL and SASVGT sheets is transformed to the same 7-column Dutch format and filtered to `TARGET_YEAR`.

### 10. Append not-measured (NM) rows

Parameters flagged as not measured receive `Resultaat = NM` with empty location, fraction, and date fields.

### 11. Export

Semicolon-separated CSV with UTF-8 BOM encoding, and Excel (`.xlsx`) workbook.

## Output columns (Dutch)

| Column | Description |
|--------|-------------|
| Unieke identiticatie meetpunt | Station ID |
| Datum staalname | Sample date (`dd/mm/YYYY`) |
| Geanalyseerde fractie | Analysed fraction |
| Unieke identificatie gemeten parameter | Parameter ID |
| Aanpak kwantificeringsgrens | LQ handling (`=`, `<`, etc.) |
| Resultaat | Measured value, `NV`, or `NM` |
| Unieke identificatie van de eenheid | Unit ID |

## Function reference

| Function | Purpose |
|----------|---------|
| `split_measured_and_not_measured_parameters` | Split parameter mapping into measured vs NM |
| `add_parameter_ids_from_mapping` | Map RWS parameter codes to ISC IDs |
| `add_station_ids_from_mapping` | Map RWS location codes to ISC station IDs |
| `add_fraction_labels_from_mapping` | Map RWS fraction codes to ISC fraction labels |
| `apply_isc_measurement_filters` | Apply BER, depth, and aquocode filters |
| `keep_lowest_aquocode_per_case` | Resolve duplicate aquocodes per measurement case |
| `build_harmonized_output` | Build harmonized Dutch output columns |
| `aggregate_compound_parameters` | Sum source parameters into compound parameters |
| `sort_by_station_parameter_date` | Sort output by station, parameter, date |
| `format_result_values` | Format results to 4 decimals, set NV for aquocode 99 |
| `select_output_columns` | Keep only the 7 Dutch output columns |
| `create_not_measured_rows` | Build NM rows for unmeasured parameters |
| `load_and_filter_chlorophyll_data` | Load and filter chlorophyll-a data |
| `run_harmonization_pipeline` | Run the full pipeline end-to-end |

## Validation checks

After running, verify:

- Row count after filtering (~6861 for 2024 in current data)
- No unexpected parameter IDs lost during filtering
- Compression warnings (incomplete groups, LQ conflicts) reviewed
- Output file opens correctly in Excel (semicolon delimiter)

## File overview

| File | Role |
|------|------|
| `04_harmonize_isc_data.ipynb` | Step-by-step pipeline notebook |
| `isc_harmonization.py` | Reusable harmonization functions |
| `04_harmonize_isc_data_README.md` | This documentation |
| `03_Exploring_duplicates.ipynb` | Exploratory duplicate/aquocode analysis (not part of production pipeline) |
| `01b_chlorofyl_data.py` | Standalone chlorophyll prep script (logic incorporated in step 9) |
