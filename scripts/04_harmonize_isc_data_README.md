# ISC data harmonization (script 04)

This script transforms Rijkswaterstaat (RWS) ISC export data into the Dutch output format required by the Internationale Scheldecommissie (ISC).

For exploratory duplicate and aquocode analysis, see `03_Exploring_duplicates.ipynb`.

## Prerequisites

- Python 3.10+
- pandas
- openpyxl (for reading/writing `.xlsx` files)

Install dependencies:

```bash
pip install pandas openpyxl
```

## How to run

### Option A: Jupyter notebook (recommended for inspection)

1. Open `scripts/04_harmonize_isc_data.ipynb` in Jupyter or VS Code.
2. Set `TARGET_YEAR` in the configuration cell (default: 2024).
3. Run all cells from top to bottom (see [Notebook steps](#notebook-steps) below).
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

`run_harmonization_pipeline` also accepts:

- `nv_parameter_ids`: extra parameter IDs to force to `NV`, in addition to any parameters flagged `SNV` in the mapping table (see [Parameter mapping "reported" codes](#parameter-mapping-reported-codes)).
- `am_classifications`: a `{station: {parameter_id: classification}}` dict used to inject manually-added biological quality rows (see [Manually-added (AM) biological quality rows](#manually-added-am-biological-quality-rows)). If omitted, no AM rows are added.

## Required input files

| File | Purpose |
|------|---------|
| `voorbeeld/isc_2023-2025/ISC_{YEAR}.xlsx` | Raw ISC measurement export for the target year |
| `mappings/locations-mapped.xlsx` | RWS location code → ISC station ID |
| `mappings/parameter_mapping_final.xlsx` (sheet: `mapping`) | Parameter combination → ISC parameter ID, unit, conversion, and `reported` classification |
| `mappings/hoedanigheid_mapped.xlsx` | Fraction code → ISC fraction label |
| `voorbeeld/isc_2023-2025/SCHAARVODDL + SASVGT_CHLfa_2023-2025.xlsx` | Chlorophyll-a measurements (separate RWS format) |

All paths are resolved relative to the repository root.

## Column naming

The pipeline uses **Dutch ISC output column names from the start**. Mapping tables and raw RWS data keep their original source column names (e.g. `locatie_code`, `parameter_code`, `eventdatum`). French column names from mapping tables are converted to Dutch when merged:

| Mapping table column | Dutch column used in pipeline |
|----------------------|-------------------------------|
| `Identitication unique de la station` | `Unieke identiticatie meetpunt` |
| `ISC_fraction` | `Geanalyseerde fractie` |

## Parameter mapping "reported" codes

The `reported` column in `parameter_mapping_final.xlsx` drives how each parameter mapping row is used in the pipeline:

| Code | Meaning | Included in `measured_mapping`? | Included in NM export? |
|------|---------|:---:|:---:|
| *(blank)* | Normal measured parameter, mapped directly from RWS data | Yes | No |
| `N` | Not measured (RWS never reports it) | No | Yes, one global row per station |
| `SK` | Needs aggregation; row maps a raw combo directly to a compound target ID, which would double-count against `aggregate_compound_parameters`. Kept in the mapping table for reference only | No | No |
| `SR` | Subset of measured parameters that are summed by `aggregate_compound_parameters` and then removed (`remove_source_rows=True`) — e.g. `6561a`/`6561b` → `6561` | Yes | No |
| `SNV` | Subset of measured parameters whose `Resultaat` is always forced to `NV` in the final output, regardless of measured value | Yes | No |
| `AM` | Added manually per station (currently the `FISH`/`IBD`/`IBGN` biological quality assessments). Not part of the RWS measurement export, and not part of the global NM list — see [Manually-added (AM) biological quality rows](#manually-added-am-biological-quality-rows) | No | No |

`split_measured_and_not_measured_parameters` splits the mapping table into `measured_mapping`, `not_measured_mapping`, `am_mapping`, `sk_mapping`, and `snv_mapping`, and prints a breakdown of all of these counts (including the `SR`/`SNV` subgroups of `measured_mapping`).

## Processing steps

### 1. Load data and mappings

Raw measurements and the mapping tables are loaded, then split via `split_measured_and_not_measured_parameters` (see codes above).

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
- `event_aquocode` in `[0, 3, 90, 99]`

(There is no longer a sample-depth filter — `bemonsteringshoogte_code` is not checked.)

### 5. Resolve duplicates with different aquocodes

For identical station + date + fraction + parameter + unit, only the row with the **lowest** valid aquocode is kept; cases with higher-aquocode duplicates are logged.

### 6. Build harmonized output

- Sort by station, date, parameter
- Format date as `Datum staalname` (`dd/mm/YYYY`)
- Compute `Resultaat`: `event_waarde × conversion`
- Set `Aanpak kwantificeringsgrens` to `=` when value is numeric and symbol is missing

### 7. Aggregate compound parameters

Some ISC parameters are sums (or differences) of other parameters, computed per station/day group by `aggregate_compound_parameters`. Currently active in the notebook and `run_harmonization_pipeline`:

| Target ID | Source IDs | Remove sources? |
|-----------|------------|-----------------|
| 1774 | 1283, 1629, 1630 | No |
| 5534 | 1103, 1181, 1173, 1207 | No |
| 6561 | 6561a, 6561b | Yes |

Additional aggregations (1319, 5537, 7706) are supported by the same function but are currently disabled/commented out.

For each aggregation, the pipeline logs: incomplete same-day groups, LQ symbol conflicts (tie-break: `<` preferred over `=`), and aquocode conflicts (tie-break: highest aquocode kept).

### 8. Format, force NV, and select output columns

- Sort by station, parameter, date (`sort_by_station_parameter_date`)
- Format numeric `Resultaat` values to 4 decimal places (as text), and set `Resultaat` to `NV` when aquocode is 99 (`format_result_values`)
- Force `Resultaat` to `NV` for any parameter ID flagged `SNV` in the mapping table (`set_nv_for_parameter_ids`, using `get_snv_parameter_ids(snv_mapping)`) — this runs immediately after `format_result_values` so both NV mechanisms are visible together
- Keep the 7 Dutch output columns (`select_output_columns`)

### 9. Append chlorophyll-a

Chlorophyll data from the SCHAARVODDL and SASVGT sheets is transformed to the same 7-column Dutch format, filtered to `TARGET_YEAR` (`load_and_filter_chlorophyll_data`), and appended to the harmonized output (`combine_harmonized_and_chlorophyll`).

### 10. Manually-added (AM) biological quality rows

See [Manually-added (AM) biological quality rows](#manually-added-am-biological-quality-rows) below (`create_am_biological_quality_rows`).

### 11. Append not-measured (NM) rows and finalize

`create_not_measured_and_finalize` builds two tiers of NM rows and appends them:

- **Global NM rows** (`create_not_measured_global_rows`): one row per `N`-flagged parameter mapping entry, expanded across every station in the dataset. `Resultaat = "NM"`, with empty fraction and date.
- **Local NM rows** (`create_not_measured_local_rows`): per station, compares the parameter+fraction+unit combinations actually present against the full set of combinations expected across all stations, and creates an `NM` row for each missing combination at that station. This is what catches, e.g., a station missing one of the `FISH`/`IBD`/`IBGN` biological assessments.

### 12. Export

Semicolon-separated CSV with UTF-8 BOM encoding, and Excel (`.xlsx`) workbook, both with every column exported as text.

## Manually-added (AM) biological quality rows

`FISH`, `IBD`, and `IBGN` are biological quality assessments (fish, diatoms, macro-invertebrates) that are not part of the RWS measurement export. They are reported per water body / station group as a classification — `Goed (Bon)` or `Matig (Moyen)` — sourced manually from a separate RWS reporting table, not from `ISC_{YEAR}.xlsx`.

These three parameters are flagged `reported = "AM"` in the parameter mapping, so they are excluded from both the measured pipeline and the global NM export.

In the notebook (and via `run_harmonization_pipeline(..., am_classifications=...)`), a manually maintained dictionary maps each station to its classification per parameter:

```python
am_classifications = {
    "NL89_SASVGT": {"IBGN": "Goed (Bon)", "IBD": "Goed (Bon)", "FISH": "Goed (Bon)"},
    "NL89_WISSKKE": {"IBGN": "Goed (Bon)", "IBD": "Matig (Moyen)"},
    # ... one entry per station; a parameter can be omitted if not assessed there
}
```

`create_am_biological_quality_rows(am_classifications, am_mapping, output_with_chlorophyll, default_date=f"31/12/{TARGET_YEAR}")`:

- Looks up the correct unit for each parameter from `am_mapping` (the `reported == "AM"` subset of the parameter mapping).
- Builds one output row per station/parameter with `Resultaat` set to the classification text, `Datum staalname` set to the last day of the target year (`31/12/{YEAR}`), and empty fraction/LQ.
- Appends the rows to the combined harmonized+chlorophyll output and prints an Input/Output row and ISC-combination summary.

Any station/parameter combination **not** present in `am_classifications` is automatically picked up as a local NM row in the next step (step 11), rather than silently missing.

## Output columns (Dutch)

| Column | Description |
|--------|-------------|
| Unieke identiticatie meetpunt | Station ID |
| Datum staalname | Sample date (`dd/mm/YYYY`) |
| Geanalyseerde fractie | Analysed fraction |
| Unieke identificatie gemeten parameter | Parameter ID |
| Aanpak kwantificeringsgrens | LQ handling (`=`, `<`, etc.) |
| Resultaat | Measured value, `NV`, `NM`, or an AM classification (`Goed (Bon)` / `Matig (Moyen)`) |
| Unieke identificatie van de eenheid | Unit ID |

## Notebook steps

The notebook (`04_harmonize_isc_data.ipynb`) is organized as:

1. Load inputs
2. Map, filter, and harmonize measurements
3. Compress compound parameters
4. Format and select output columns (includes forcing `SNV` parameters to `NV`)
5. Load chlorophyll-a data and combine with harmonized data
6. Add manually-added (AM) biological quality rows
7. Create not-measured (NM) rows and finalize output
8. Export

Each pipeline function prints a numbered `STEP` header with an Input/Output row and ISC-combination summary, so re-running any single cell shows exactly what changed.

## Function reference

| Function | Purpose |
|----------|---------|
| `split_measured_and_not_measured_parameters` | Split parameter mapping into `measured_mapping`, `not_measured_mapping`, `am_mapping`, `sk_mapping`, `snv_mapping` |
| `get_snv_parameter_ids` | Return parameter IDs flagged `SNV` (forced to NV in output) |
| `add_parameter_ids_from_mapping` | Map RWS parameter codes to ISC IDs |
| `add_station_ids_from_mapping` | Map RWS location codes to ISC station IDs |
| `add_fraction_labels_from_mapping` | Map RWS fraction codes to ISC fraction labels |
| `apply_isc_measurement_filters` | Apply BER and aquocode filters |
| `keep_lowest_aquocode_per_case` | Resolve duplicates with different aquocodes per measurement case |
| `build_harmonized_output` | Build harmonized Dutch output columns |
| `aggregate_compound_parameters` | Sum/subtract source parameters into compound parameters, with LQ/aquocode conflict diagnostics |
| `sort_by_station_parameter_date` | Sort output by station, parameter, date |
| `format_result_values` | Format results to 4 decimals, set `NV` for aquocode 99 |
| `set_nv_for_parameter_ids` | Force `Resultaat` to `NV` for a given list of parameter IDs |
| `select_output_columns` | Keep only the 7 Dutch output columns |
| `load_and_filter_chlorophyll_data` | Load and filter chlorophyll-a data |
| `combine_harmonized_and_chlorophyll` | Append chlorophyll rows to the harmonized output |
| `create_am_biological_quality_rows` | Build and append manually-added (AM) biological quality rows |
| `create_not_measured_global_rows` | Build global NM rows for parameters flagged `N`, expanded per station |
| `create_not_measured_local_rows` | Build per-station NM rows for station-level missing ISC combinations |
| `create_not_measured_and_finalize` | Combine global + local NM rows and produce the final dataset |
| `export_final_output` | Save final output as CSV and Excel |
| `run_harmonization_pipeline` | Run the full pipeline end-to-end |

## Validation checks

After running, verify:

- Row count after filtering
- No unexpected parameter IDs lost during filtering
- Compression warnings (incomplete groups, LQ/aquocode conflicts) reviewed
- Local NM step: check that stations missing an AM parameter (`FISH`/`IBD`/`IBGN`) or any other expected combination are flagged as expected
- Output file opens correctly in Excel (semicolon delimiter)

## File overview

| File | Role |
|------|------|
| `04_harmonize_isc_data.ipynb` | Step-by-step pipeline notebook |
| `isc_harmonization.py` | Reusable harmonization functions |
| `04_harmonize_isc_data_README.md` | This documentation |
| `03_Exploring_duplicates.ipynb` | Exploratory duplicate/aquocode analysis (not part of production pipeline) |
| `01b_chlorofyl_data.py` | Standalone chlorophyll prep script (logic incorporated in step 9) |
