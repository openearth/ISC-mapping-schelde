"""ISC data harmonization helpers.

Transforms Rijkswaterstaat (RWS) ISC export data into the Dutch output
format required by the Internationale Scheldecommissie (ISC).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

VALID_AQUOCODES = [0, 3, 90, 99]

# Dutch ISC output columns (used throughout the pipeline)
COL_STATION = "Unieke identiticatie meetpunt"
COL_FRACTION = "Geanalyseerde fractie"
COL_DATE = "Datum staalname"
COL_LQ = "Aanpak kwantificeringsgrens"
COL_RESULT = "Resultaat"
COL_PARAMETER = "Unieke identificatie gemeten parameter"
COL_UNIT = "Unieke identificatie van de eenheid"

OUTPUT_COLUMNS = [
    COL_STATION,
    COL_DATE,
    COL_FRACTION,
    COL_PARAMETER,
    COL_LQ,
    COL_RESULT,
    COL_UNIT,
]

# Source-data column names from RWS export (kept as-is during processing)
COL_RAW_VALUE = "event_waarde"
COL_RAW_UNIT_CODE = "eenheid_code"
COL_CONVERSION = "conversion"
COL_AQUOCODE = "event_aquocode"

# RWS source keys that define a unique substance combination
COMBINATION_COLS = [
    "parameter_code",
    "grootheid_code",
    "hoedanigheid_code",
    "eenheid_code",
]

ISC_COMBINATION_COLS = [COL_PARAMETER, COL_FRACTION, COL_UNIT]
ISC_COMBINATION_LABEL = "ISC combinations"


def count_combinations(
    df: pd.DataFrame,
    combination_cols: list[str] | None = None,
) -> int | None:
    """Count unique combinations for the requested columns in a dataframe."""
    cols = combination_cols or COMBINATION_COLS
    if not all(col in df.columns for col in cols):
        return None

    combos = df[cols].copy()
    for col in cols:
        combos[col] = (
            combos[col]
            .astype("string")
            .str.strip()
            .fillna("<missing>")
            .replace({"nan": "<missing>", "None": "<missing>"})
        )

    return combos.drop_duplicates().shape[0]


def print_step_header(title: str, step: int | None = None) -> None:
    """Print a visible header for a pipeline step."""
    label = f"STEP {step}: {title}" if step is not None else title
    print("\n" + "=" * 70)
    print(label)
    print("=" * 70)


def summarize_dataframe(
    df: pd.DataFrame,
    *,
    station_col: str | None = COL_STATION,
    fraction_col: str | None = COL_FRACTION,
    combination_cols: list[str] | None = None,
    combination_label: str = "combinations",
) -> dict[str, int | str | None]:
    """Collect row counts and key dimensions from a dataframe."""
    summary: dict[str, int | str | None] = {"rows": len(df)}

    n_combinations = count_combinations(df, combination_cols=combination_cols)
    if n_combinations is not None:
        summary[combination_label] = n_combinations
    if station_col and station_col in df.columns:
        summary["stations"] = df[station_col].nunique(dropna=True)
    if fraction_col and fraction_col in df.columns:
        summary["fractions"] = df[fraction_col].nunique(dropna=True)

    return summary


def print_data_summary(
    label: str,
    summary: dict[str, int | str | None],
    *,
    indent: int = 2,
    combination_label: str = "combinations",
) -> None:
    """Print a labelled data summary block."""
    prefix = " " * indent
    parts = [f"{prefix}{label}: {summary.get('rows', 0):,} rows"]

    if combination_label in summary:
        parts.append(f"{summary[combination_label]} {combination_label}")
    if "stations" in summary:
        parts.append(f"{summary['stations']} stations")
    if "fractions" in summary:
        parts.append(f"{summary['fractions']} fractions")

    print(" | ".join(parts))


def format_combination(row: pd.Series, match_cols: list[str] | None = None) -> str:
    """Format one RWS combination as readable text."""
    cols = match_cols or COMBINATION_COLS
    return ", ".join(f"{col}={row[col]}" for col in cols)


def print_combination_mapping_diagnostics(mapping: pd.DataFrame, match_cols: list[str]) -> None:
    """Print combination-level diagnostics for the parameter mapping table."""
    n_combinations = len(mapping)
    print(f"  Mapping entries available: {n_combinations:,} unique combinations")

    duplicate_combos = mapping[mapping.duplicated(subset=match_cols, keep=False)].sort_values(match_cols)
    if not duplicate_combos.empty:
        print(
            f"  ! {len(duplicate_combos)} mapping row(s) share the same combination "
            f"but point to different ISC targets"
        )
        for combo_key, group in duplicate_combos.groupby(match_cols, dropna=False):
            if not isinstance(combo_key, tuple):
                combo_key = (combo_key,)
            combo = ", ".join(f"{col}={val}" for col, val in zip(match_cols, combo_key))
            targets = group[COL_PARAMETER].astype(str).unique().tolist()
            print(f"    - {combo} -> ISC targets {targets}")


def print_unused_combinations(
    mapping: pd.DataFrame,
    measurements: pd.DataFrame,
    match_cols: list[str],
) -> None:
    """Print combinations present in the mapping but missing from the dataset."""
    mapping_combos = mapping[match_cols].drop_duplicates()
    data_combos = measurements[match_cols].drop_duplicates()
    unused = mapping_combos.merge(
        data_combos.assign(_present=1),
        on=match_cols,
        how="left",
    )
    unused = unused[unused["_present"].isna()].drop(columns="_present")

    if unused.empty:
        print(f"  > All {len(mapping_combos):,} mapped combinations appear in the dataset")
        return

    print(f"  > {len(unused):,} combination(s) in mapping have no rows in this dataset:")
    for _, row in unused.iterrows():
        print(f"    - {format_combination(row, match_cols)}")


def normalize_combination_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return unique RWS combinations with normalized string values."""
    missing = [col for col in COMBINATION_COLS if col not in df.columns]
    if missing:
        raise KeyError(f"Missing combination columns: {missing}")

    combos = df[COMBINATION_COLS].copy()
    for col in COMBINATION_COLS:
        combos[col] = (
            combos[col]
            .astype("string")
            .str.strip()
            .fillna("<missing>")
            .replace({"nan": "<missing>", "None": "<missing>"})
        )
    return combos.drop_duplicates()


def combination_tuples(df: pd.DataFrame) -> set[tuple]:
    """Return a set of combination tuples from a dataframe."""
    normalized = normalize_combination_columns(df)
    return set(map(tuple, normalized.to_numpy()))


def format_combination_tuple(combo: tuple) -> str:
    """Format a combination tuple for display."""
    combo_dict = dict(zip(COMBINATION_COLS, combo))
    return format_combination(pd.Series(combo_dict))


def normalize_isc_combination_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return unique ISC combinations with normalized string values."""
    missing = [col for col in ISC_COMBINATION_COLS if col not in df.columns]
    if missing:
        raise KeyError(f"Missing ISC combination columns: {missing}")

    combos = df[ISC_COMBINATION_COLS].copy()
    for col in ISC_COMBINATION_COLS:
        combos[col] = (
            combos[col]
            .astype("string")
            .str.strip()
            .fillna("<missing>")
            .replace({"nan": "<missing>", "None": "<missing>"})
        )
    return combos.drop_duplicates()


def isc_combination_tuples(df: pd.DataFrame) -> set[tuple]:
    """Return a set of ISC combination tuples from a dataframe."""
    normalized = normalize_isc_combination_columns(df)
    return set(map(tuple, normalized.to_numpy()))


def format_isc_combination_tuple(combo: tuple) -> str:
    """Format one ISC combination tuple for display."""
    combo_dict = dict(zip(ISC_COMBINATION_COLS, combo))
    return (
        f"parameter={combo_dict[COL_PARAMETER]}, "
        f"fraction={combo_dict[COL_FRACTION]}, "
        f"unit={combo_dict[COL_UNIT]}"
    )


def format_chlorophyll_combination(row: pd.Series) -> str:
    """Format a chlorophyll output row as a readable combination label."""
    unit = str(row[COL_UNIT]).replace("µ", "u")
    return (
        f"parameter={row[COL_PARAMETER]}, "
        f"fraction={row[COL_FRACTION]}, "
        f"unit={unit} (chlorophyll)"
    )


def format_not_measured_mapping_row(row: pd.Series) -> str:
    """Format one NM mapping row for the station report."""
    param_id = row[COL_PARAMETER]
    name = row.get("ISC_Parameter")
    name_part = f" ({name})" if pd.notna(name) and str(name).strip() else ""

    combo_parts = []
    for col in COMBINATION_COLS:
        value = row.get(col)
        if pd.isna(value) or str(value).strip() in ("", "nan", "None"):
            combo_parts.append(f"{col}=<missing>")
        else:
            combo_parts.append(f"{col}={value}")

    unit = row[COL_UNIT] if pd.notna(row.get(COL_UNIT)) else "<missing>"
    return (
        f"ISC parameter {param_id}{name_part} | "
        f"{', '.join(combo_parts)} | unit={unit}"
    )


def print_not_measured_mapping_summary(not_measured_mapping: pd.DataFrame) -> None:
    """Print every NM mapping row so none are hidden by deduplication."""
    if not_measured_mapping.empty:
        print("  Globally not measured (NM): 0 mapping rows")
        return

    mapping = not_measured_mapping.copy()
    unique_output_rows = (
        mapping[[COL_PARAMETER, COL_UNIT]]
        .dropna(subset=[COL_PARAMETER])
        .drop_duplicates()
    )

    print(f"  Globally not measured (NM): {len(mapping):,} mapping row(s)")
    if len(unique_output_rows) != len(mapping):
        print(
            f"  > {len(unique_output_rows):,} unique parameter+unit pair(s) in NM export "
            f"({len(mapping) - len(unique_output_rows):,} duplicate mapping row(s) merged)"
        )

    sort_key = mapping[COL_PARAMETER].astype(str)
    for _, row in mapping.assign(_sort_key=sort_key).sort_values("_sort_key").iterrows():
        print(f"    - {format_not_measured_mapping_row(row)}")


def print_station_combination_report(
    measured_data: pd.DataFrame,
    chlorophyll_data: pd.DataFrame,
    measured_mapping: pd.DataFrame,
    not_measured_mapping: pd.DataFrame,
) -> None:
    """Print missing ISC combinations per station before export."""
    print_step_header("Station combination report", step=16)

    expected_source = measured_mapping if all(
        col in measured_mapping.columns for col in ISC_COMBINATION_COLS
    ) else measured_data
    expected_combos = normalize_isc_combination_columns(expected_source)
    expected_set = isc_combination_tuples(expected_combos)
    print(f"  Expected ISC combinations: {len(expected_set):,}")

    print_not_measured_mapping_summary(not_measured_mapping)

    if COL_STATION not in measured_data.columns:
        raise KeyError(f"Missing required column for report: {COL_STATION}")

    stations_measured = set(measured_data[COL_STATION].dropna().unique())
    stations_chlorophyll = (
        set(chlorophyll_data[COL_STATION].dropna().unique())
        if len(chlorophyll_data) > 0 and COL_STATION in chlorophyll_data.columns
        else set()
    )
    all_stations = sorted(stations_measured | stations_chlorophyll)

    for station in all_stations:
        station_data = measured_data[measured_data[COL_STATION] == station]
        measured_set = isc_combination_tuples(station_data) if len(station_data) else set()
        missing_set = expected_set - measured_set

        chl_at_station = (
            chlorophyll_data[chlorophyll_data[COL_STATION] == station]
            if len(chlorophyll_data) > 0 and COL_STATION in chlorophyll_data.columns
            else chlorophyll_data.iloc[0:0]
        )
        chl_set = (
            isc_combination_tuples(chl_at_station)
            if len(chl_at_station)
            else set()
        )

        print(f"\n  Station: {station}")
        print(
            f"  > Missing ISC combinations at station: {len(missing_set):,} / {len(expected_set):,}"
        )

        if missing_set:
            print(f"  Not measured at this station ({len(missing_set):,}):")
            print("    (expected ISC combinations only; NM parameters are listed globally above)")
            for combo in sorted(missing_set):
                print(f"    - {format_isc_combination_tuple(combo)}")
        else:
            print("  > All expected ISC combinations are present at this station")


def print_row_change(before: int, after: int, *, reason: str) -> None:
    """Print how many rows were kept or dropped between steps."""
    dropped = before - after
    if dropped > 0:
        pct = (dropped / before * 100) if before else 0
        print(f"  - {dropped:,} rows dropped ({pct:.1f}%) - {reason}")
    elif dropped < 0:
        print(f"  + {-dropped:,} rows added - {reason}")
    else:
        print(f"  > No row change - {reason}")


def print_loaded_inputs(
    raw_measurements: pd.DataFrame,
    location_mapping: pd.DataFrame,
    parameter_mapping: pd.DataFrame,
    fraction_mapping: pd.DataFrame,
) -> None:
    """Print a summary of loaded input files."""
    print_step_header("Load input files", step=0)
    print(f"  > Raw measurements: {len(raw_measurements):,} rows")
    print(f"  > Location mapping: {len(location_mapping):,} rows")
    print(f"  > Parameter mapping: {len(parameter_mapping):,} rows")
    print(f"  > Fraction mapping: {len(fraction_mapping):,} rows")


def get_repo_root() -> Path:
    """Return repository root (parent of the scripts folder)."""
    return Path(__file__).resolve().parent.parent


def split_measured_and_not_measured_parameters(
    parameter_mapping: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split parameter mapping into measured, not-measured (NM), manually-added (AM), and aggregation-only (SK) parameters."""
    print_step_header("Split parameter mapping", step=1)

    total = len(parameter_mapping)
    not_measured_mapping = parameter_mapping[
        parameter_mapping["reported"].isin(["N"])
    ].copy()
    measured_mapping = parameter_mapping[
        ~parameter_mapping["reported"].isin(["N", "SK", "AM"])
    ].copy()
    sk_mapping = parameter_mapping[
        parameter_mapping["reported"].isin(["SK"])
    ].copy()
    am_mapping = parameter_mapping[
        parameter_mapping["reported"].isin(["AM"])
    ].copy()
    sum_and_remove_mapping = measured_mapping[
        measured_mapping["reported"].isin(["SR"])
    ]
    snv_mapping = measured_mapping[
        measured_mapping["reported"].isin(["SNV"])
    ].copy()

    print(f"  Mapping table: {total:,} rows total")
    print(f"  > Measured combinations (used in pipeline): {len(measured_mapping):,}")
    print(
        f"    - of which needs summing + removal after aggregation (reported = SR): "
        f"{len(sum_and_remove_mapping):,}"
    )
    print(
        f"    - of which forced to NV in output (reported = SNV): "
        f"{len(snv_mapping):,}"
    )
    print(f"  > Not measured (NM, appended at end): {len(not_measured_mapping):,}")
    print(
        f"  > Needs aggregation, kept out of direct mapping (reported = SK): "
        f"{len(sk_mapping):,}"
    )
    print(
        f"  > Added manually per station, kept out of direct mapping and NM export "
        f"(reported = AM): {len(am_mapping):,}"
    )

    return measured_mapping, not_measured_mapping, am_mapping, sk_mapping, snv_mapping


def get_snv_parameter_ids(snv_mapping: pd.DataFrame) -> list[str]:
    """Return unique parameter IDs flagged reported = 'SNV' (forced to NV in output)."""
    if COL_PARAMETER not in snv_mapping.columns:
        raise KeyError(f"Missing required column in snv_mapping: {COL_PARAMETER}")

    return (
        snv_mapping[COL_PARAMETER]
        .dropna()
        .astype(str)
        .str.strip()
        .drop_duplicates()
        .tolist()
    )


def add_parameter_ids_from_mapping(
    measurements: pd.DataFrame,
    parameter_mapping: pd.DataFrame,
) -> pd.DataFrame:
    """Map RWS parameter combinations to ISC parameter IDs, units, and conversions."""
    match_cols = COMBINATION_COLS.copy()
    target_cols = [COL_PARAMETER, COL_UNIT, COL_CONVERSION]

    mapping = parameter_mapping[match_cols + target_cols].copy()

    for col in match_cols:
        mapping[col] = mapping[col].astype(str).str.strip()
        measurements[col] = measurements[col].astype(str).str.strip()

    print_step_header("Map parameter combinations", step=2)

    input_combos = count_combinations(measurements)
    print_data_summary("Input", summarize_dataframe(measurements))
    if input_combos is not None:
        print(f"  > {input_combos:,} unique combinations in raw data")

    duplicate_combos_before_dedup = mapping[mapping.duplicated(subset=match_cols, keep=False)]
    if not duplicate_combos_before_dedup.empty:
        print(
            f"  ! Warning: {len(duplicate_combos_before_dedup)} mapping row(s) share "
            f"the same combination but have different ISC targets"
        )
        for combo_key, group in duplicate_combos_before_dedup.groupby(match_cols, dropna=False):
            if not isinstance(combo_key, tuple):
                combo_key = (combo_key,)
            combo = ", ".join(f"{col}={val}" for col, val in zip(match_cols, combo_key))
            targets = group[COL_PARAMETER].astype(str).unique().tolist()
            print(f"    - {combo} -> ISC targets {targets}")

    mapping = mapping.drop_duplicates(subset=match_cols, keep="first")
    print_combination_mapping_diagnostics(mapping, match_cols)

    rows_before = len(measurements)
    measurements = measurements.merge(mapping, on=match_cols, how="left")
    unmapped = measurements[COL_PARAMETER].isna().sum()
    measurements = measurements[measurements[COL_PARAMETER].notna()]

    output_summary = summarize_dataframe(measurements)
    print_data_summary("Output", output_summary)
    print_row_change(rows_before, len(measurements), reason="no matching combination in mapping")

    if unmapped:
        print(f"  > {unmapped:,} rows had no combination match and were removed")
    print_unused_combinations(mapping, measurements, match_cols)

    if len(measurements) == 0:
        print("  ! No data remaining after combination mapping")

    return measurements


def add_station_ids_from_mapping(
    measurements: pd.DataFrame,
    location_mapping: pd.DataFrame,
) -> pd.DataFrame:
    """Map RWS location codes to ISC station IDs (Dutch column name)."""
    mapping = location_mapping[["locatie_code", "Identitication unique de la station"]].rename(
        columns={"Identitication unique de la station": COL_STATION}
    )
    print_step_header("Map locations", step=3)

    rows_before = len(measurements)
    input_summary = summarize_dataframe(measurements, fraction_col=None)
    print_data_summary("Input", input_summary)
    print(f"  Location codes in mapping: {mapping['locatie_code'].nunique():,}")

    measurements = measurements.merge(mapping, on="locatie_code", how="left")

    missing_count = int(measurements[COL_STATION].isna().sum())
    output_summary = summarize_dataframe(measurements, fraction_col=None)
    print_data_summary("Output", output_summary)
    print_row_change(rows_before, len(measurements), reason="location mapping does not drop rows")

    if missing_count:
        print(f"  ! {missing_count:,} rows have no station ID (locatie_code not in mapping)")
    else:
        print("  > All rows matched to a station ID")

    return measurements


def add_fraction_labels_from_mapping(
    measurements: pd.DataFrame,
    fraction_mapping: pd.DataFrame,
) -> pd.DataFrame:
    """Map RWS fraction codes to ISC fraction labels (Dutch column name)."""
    mapping = fraction_mapping.rename(
        columns={
            "hoedanigheid_code_wadar": "hoedanigheid_code",
            "ISC_fraction": COL_FRACTION,
        }
    )[["hoedanigheid_code", COL_FRACTION]]

    print_step_header("Map fractions", step=4)

    rows_before = len(measurements)
    input_summary = summarize_dataframe(measurements)
    print_data_summary("Input", input_summary)
    print(f"  Fraction codes in mapping: {mapping['hoedanigheid_code'].nunique():,}")

    measurements = measurements.merge(mapping, on="hoedanigheid_code", how="left")

    missing_count = int(measurements[COL_FRACTION].isna().sum())
    output_summary = summarize_dataframe(measurements)
    print_data_summary("Output", output_summary)
    print_row_change(rows_before, len(measurements), reason="fraction mapping does not drop rows")

    if missing_count:
        print(f"  ! {missing_count:,} rows have no fraction label (hoedanigheid_code not in mapping)")
    else:
        print("  > All rows matched to a fraction label")

    return measurements


def apply_isc_measurement_filters(
    measurements: pd.DataFrame,
) -> pd.DataFrame:
    """Apply standard ISC filters on mapped measurements."""
    print_step_header("Filter measurements", step=5)

    rows_start = len(measurements)
    combos_before = count_combinations(measurements)
    print_data_summary("Input", summarize_dataframe(measurements))
    if combos_before is not None:
        print(f"  > {combos_before:,} unique combinations")

    filtered = measurements[measurements["waardebewerkings_methode_code"] != "BER"]
    dropped_ber = rows_start - len(filtered)
    print(f"  - Exclude BER method: {len(filtered):,} rows remain ({dropped_ber:,} dropped)")

    rows_before_aquo = len(filtered)
    filtered = filtered[filtered[COL_AQUOCODE].isin(VALID_AQUOCODES)]
    dropped_aquo = rows_before_aquo - len(filtered)
    print(
        f"  - Keep aquocodes {VALID_AQUOCODES}: "
        f"{len(filtered):,} rows remain ({dropped_aquo:,} dropped)"
    )

    combos_after = count_combinations(filtered)
    combos_lost = None
    if combos_before is not None and combos_after is not None:
        before_set = set(map(tuple, measurements[COMBINATION_COLS].drop_duplicates().to_numpy()))
        after_set = set(map(tuple, filtered[COMBINATION_COLS].drop_duplicates().to_numpy()))
        lost_combos = before_set - after_set
        combos_lost = len(lost_combos)

    print_data_summary("Output", summarize_dataframe(filtered))
    print_row_change(rows_start, len(filtered), reason="ISC quality filters applied")

    if combos_after is not None:
        print(f"  > {combos_after:,} unique combinations remain")
    if combos_lost:
        print(f"  ! {combos_lost} combination(s) lost by filtering:")
        before_set = set(map(tuple, measurements[COMBINATION_COLS].drop_duplicates().to_numpy()))
        after_set = set(map(tuple, filtered[COMBINATION_COLS].drop_duplicates().to_numpy()))
        for combo in sorted(before_set - after_set):
            combo_dict = dict(zip(COMBINATION_COLS, combo))
            print(f"    - {format_combination(pd.Series(combo_dict))}")
    elif combos_lost == 0:
        print("  > No combinations were lost during filtering")

    if len(filtered) == 0:
        print("  ! No data remaining after filtering")

    return filtered


def keep_lowest_aquocode_per_case(
    measurements: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep the row with the lowest valid aquocode for each measurement case."""
    group_cols = [
        COL_STATION,
        "eventdatum",
        COL_FRACTION,
        COL_PARAMETER,
        COL_RAW_UNIT_CODE,
    ]

    kept_rows = []
    removed_rows = []

    for _, group_df in measurements.groupby(group_cols, dropna=False):
        aquocodes_in_group = group_df[COL_AQUOCODE].tolist()
        valid_in_group = [ac for ac in aquocodes_in_group if ac in VALID_AQUOCODES]
        lowest_aquocode = min(valid_in_group) if valid_in_group else None

        row_to_keep = group_df[group_df[COL_AQUOCODE] == lowest_aquocode].iloc[0].copy()

        higher_aquocodes = [ac for ac in VALID_AQUOCODES if ac > lowest_aquocode]
        higher_present = {
            ac: aquocodes_in_group.count(ac)
            for ac in higher_aquocodes
            if ac in aquocodes_in_group
        }

        row_to_keep["has_higher_aquocodes"] = "yes" if higher_present else "no"
        row_to_keep["higher_aquocodes_info"] = str(higher_present) if higher_present else ""
        kept_rows.append(row_to_keep)

        rows_removed = group_df[group_df[COL_AQUOCODE] != lowest_aquocode]
        if len(rows_removed) > 0:
            removed_rows.extend(rows_removed.to_dict("records"))

    kept_df = pd.DataFrame(kept_rows).reset_index(drop=True)
    removed_df = pd.DataFrame(removed_rows).reset_index(drop=True)

    print_step_header("Resolve duplicates with different aquocodes", step=6)

    rows_before = len(measurements)
    print_data_summary("Input", summarize_dataframe(measurements))
    print_data_summary("Output", summarize_dataframe(kept_df))
    print_row_change(
        rows_before,
        len(kept_df),
        reason="keep lowest aquocode per station/date/fraction/parameter/unit",
    )
    print(f"  > {len(removed_df):,} duplicate rows removed")

    cases_with_alternatives = (
        int(kept_df["has_higher_aquocodes"].eq("yes").sum())
        if "has_higher_aquocodes" in kept_df.columns
        else 0
    )
    if cases_with_alternatives:
        print(
            f"  > {cases_with_alternatives:,} case(s) were duplicated with different "
            "aquocodes; the record with the lowest aquocode was kept"
        )

    if len(kept_df) == 0:
        print("  ! No data remaining after aquocode resolution")

    return kept_df, removed_df


def build_harmonized_output(measurements: pd.DataFrame) -> pd.DataFrame:
    """Transform filtered measurements into harmonized Dutch ISC columns."""
    combination_cols = [col for col in COMBINATION_COLS if col != COL_RAW_UNIT_CODE]
    columns_to_keep = [
        COL_STATION,
        "eventdatum",
        COL_FRACTION,
        COL_PARAMETER,
        "event_waarde_limietsymbool",
        COL_RAW_VALUE,
        COL_RAW_UNIT_CODE,
        COL_UNIT,
        COL_CONVERSION,
        COL_AQUOCODE,
        *combination_cols,
    ]

    missing_cols = [c for c in columns_to_keep if c not in measurements.columns]
    if missing_cols:
        raise KeyError(f"Missing required columns: {missing_cols}")

    result_df = measurements[columns_to_keep].copy()
    result_df["eventdatum"] = pd.to_datetime(result_df["eventdatum"], errors="coerce")

    result_df = result_df.sort_values(
        by=[COL_STATION, "eventdatum", COL_PARAMETER],
        ascending=[True, True, True],
        na_position="last",
        kind="mergesort",
    ).reset_index(drop=True)

    result_df[COL_DATE] = result_df["eventdatum"].dt.strftime("%d/%m/%Y")
    result_df[COL_RESULT] = result_df[COL_RAW_VALUE] * result_df[COL_CONVERSION]

    numeric_mask = (
        pd.to_numeric(result_df[COL_RAW_VALUE], errors="coerce").notna()
        & result_df["event_waarde_limietsymbool"].isna()
    )
    result_df.loc[numeric_mask, "event_waarde_limietsymbool"] = "="
    result_df[COL_LQ] = result_df["event_waarde_limietsymbool"]

    final_cols = [
        COL_STATION,
        COL_DATE,
        COL_FRACTION,
        COL_PARAMETER,
        COL_LQ,
        COL_RESULT,
        COL_UNIT,
        COL_RAW_VALUE,
        COL_RAW_UNIT_CODE,
        COL_CONVERSION,
        COL_AQUOCODE,
        *combination_cols,
    ]
    result_df = result_df[final_cols]

    print_step_header("Build harmonized output", step=7)

    rows_before = len(measurements)
    print_data_summary("Input", summarize_dataframe(measurements))
    print_data_summary("Output", summarize_dataframe(result_df))
    print_row_change(rows_before, len(result_df), reason="column transformation only, no rows dropped")

    lq_filled = int(result_df[COL_LQ].eq("=").sum())
    print(f"  > {lq_filled:,} rows received default LQ symbol '='")

    return result_df


def aggregate_lq_symbol(series: pd.Series):
    """Return a single LQ symbol, or a list when symbols differ within a group."""
    values = series.dropna().tolist()
    if not values:
        return None

    unique_values = list(dict.fromkeys(values))
    if len(unique_values) == 1:
        return unique_values[0]
    return unique_values


def aggregate_lq_list(series: pd.Series) -> list[str]:
    """Return unique non-empty LQ symbols in encounter order."""
    values = []
    for value in series.dropna().tolist():
        text = str(value).strip()
        if text:
            values.append(text)
    return list(dict.fromkeys(values))


def select_preferred_lq_symbol(series: pd.Series) -> str | None:
    """Select one LQ symbol, preferring '<' over '=' when both are present."""
    symbols = aggregate_lq_list(series)
    if not symbols:
        return None
    if "<" in symbols:
        return "<"
    if "=" in symbols:
        return "="
    return symbols[0]


def aggregate_aquocode_list(series: pd.Series) -> list[int | float | str]:
    """Return unique aquocodes as a sorted numeric list when possible."""
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if not numeric.empty:
        values = sorted(set(numeric.tolist()))
        out: list[int | float | str] = []
        for value in values:
            value_float = float(value)
            out.append(int(value_float) if value_float.is_integer() else value_float)
        return out

    text_values = []
    for value in series.dropna().tolist():
        text = str(value).strip()
        if text:
            text_values.append(text)
    return list(dict.fromkeys(text_values))


def select_highest_aquocode(series: pd.Series) -> int | float | None:
    """Select the highest numeric aquocode from one aggregation group."""
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None

    highest = float(numeric.max())
    return int(highest) if highest.is_integer() else highest


def aggregate_unique_values(series: pd.Series) -> list:
    """Return unique non-empty values in encounter order."""
    values = []
    for value in series.tolist():
        if pd.isna(value):
            continue
        if isinstance(value, str):
            text = value.strip()
            if not text:
                continue
            values.append(text)
        else:
            values.append(value)

    unique_values = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return unique_values


def select_unique_or_empty(series: pd.Series):
    """Return one unique value, or empty text when multiple values are present."""
    unique_values = aggregate_unique_values(series)
    if len(unique_values) == 1:
        return unique_values[0]
    return ""


def aggregate_compound_parameters(
    df: pd.DataFrame,
    source_param_ids: list[str | int],
    target_param_id: str | int,
    source_ops: list[str] | None = None,
    source_fractions: list[str] | None = None,
    unit_source_param_id: str | int = 0,
    group_cols: list[str] | None = None,
    sum_cols: list[str] | None = None,
    list_cols: list[str] | None = None,
    remove_source_rows: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Aggregate source parameters into one target per case, with + / - per source."""
    source_param_ids = [str(x) for x in source_param_ids]
    target_param_id = str(target_param_id)
    expected_ids = set(source_param_ids)

    if source_ops is None:
        source_ops = ["+"] * len(source_param_ids)
    else:
        source_ops = [str(op).strip() for op in source_ops]

    if len(source_ops) != len(source_param_ids):
        raise ValueError("source_ops must have the same length as source_param_ids")

    invalid_ops = [op for op in source_ops if op not in {"+", "-"}]
    if invalid_ops:
        raise ValueError(
            f"source_ops may only contain '+' or '-'. Invalid: {invalid_ops}"
        )

    if len(set(source_param_ids)) != len(source_param_ids):
        raise ValueError("source_param_ids must be unique when using source_ops")

    unit_source_param: str | None = None
    if unit_source_param_id not in (0, "0", None, ""):
        unit_source_param = str(unit_source_param_id)
        if unit_source_param not in source_param_ids:
            raise ValueError(
                "unit_source_param_id must be one of source_param_ids when provided"
            )

    fraction_map: dict[str, str] | None = None
    if source_fractions is not None:
        source_fractions = [str(f).strip() for f in source_fractions]
        if len(source_fractions) != len(source_param_ids):
            raise ValueError("source_fractions must have the same length as source_param_ids")
        if COL_FRACTION not in df.columns:
            raise KeyError(f"Missing required column for source_fractions: {COL_FRACTION}")
        fraction_map = dict(zip(source_param_ids, source_fractions))

    sign_map = {
        param_id: (1 if op == "+" else -1)
        for param_id, op in zip(source_param_ids, source_ops)
    }

    if group_cols is None:
        group_cols = [
            COL_STATION,
            COL_DATE,
        ]

    if sum_cols is None:
        sum_cols = [COL_RESULT, COL_RAW_VALUE]

    if list_cols is None:
        list_cols = []

    compression_combination_cols = [COL_PARAMETER, COL_FRACTION, COL_UNIT]
    compression_combination_label = "ISC combinations"

    # These are handled explicitly to keep both list and selected scalar columns.
    managed_base_cols = {
        COL_AQUOCODE,
        COL_LQ,
        COL_FRACTION,
        COL_UNIT,
        COL_CONVERSION,
        COL_RAW_UNIT_CODE,
        "grootheid_code",
        "hoedanigheid_code",
        COL_PARAMETER,
    }
    list_cols = [c for c in list_cols if c not in managed_base_cols]

    rows_before = len(df)

    print_step_header(f"Aggregate compound combinations -> {target_param_id}")
    print(f"  Source combinations (by ISC target): {source_param_ids}")
    print(f"  Source operations (+/-): {source_ops}")
    if fraction_map is not None:
        print(f"  Source fractions per parameter: {fraction_map}")
    if unit_source_param is not None:
        print(f"  Unit source parameter: {unit_source_param}")
    print(f"  Grouping keys for aggregation: {group_cols}")
    print(f"  Remove source rows after aggregation: {remove_source_rows}")
    print_data_summary(
        "Input",
        summarize_dataframe(
            df,
            combination_cols=compression_combination_cols,
            combination_label=compression_combination_label,
        ),
        combination_label=compression_combination_label,
    )

    mask = df[COL_PARAMETER].astype(str).isin(source_param_ids)
    if fraction_map is not None:
        fraction_mask = pd.Series(False, index=df.index)
        param_values = df[COL_PARAMETER].astype(str)
        frac_values = df[COL_FRACTION].astype(str)
        for param_id, fraction in fraction_map.items():
            fraction_mask |= (param_values.eq(param_id) & frac_values.eq(fraction))
        mask = mask & fraction_mask

    n_source_rows = int(mask.sum())
    df_sub = df[mask].copy()

    if df_sub.empty:
        print(f"  ! No rows found for source combinations {source_param_ids} - step skipped")
        return df.copy(), pd.DataFrame(), pd.DataFrame()

    print(f"  > {n_source_rows:,} source rows matched for aggregation")

    source_counts = df_sub[COL_PARAMETER].astype(str).value_counts()
    print("  Source rows per source parameter:")
    for param_id in source_param_ids:
        count = int(source_counts.get(param_id, 0))
        print(f"    - {param_id}: {count:,} rows")

    grouped_sources = (
        df_sub.assign(_source_param=df_sub[COL_PARAMETER].astype(str))
        .groupby(group_cols, dropna=False)["_source_param"]
        .agg(lambda s: sorted(set(s)))
        .reset_index(name="available_source_params")
    )
    grouped_sources["n_available"] = grouped_sources["available_source_params"].map(len)
    grouped_sources["n_expected"] = len(source_param_ids)

    print("  Same station/day groups by number of source parameters present:")
    for n_present in range(len(source_param_ids), 0, -1):
        n_groups = int(grouped_sources["n_available"].eq(n_present).sum())
        print(f"    - {n_present} present: {n_groups:,} group(s)")

    complete_groups = grouped_sources[grouped_sources["n_available"].eq(len(source_param_ids))]
    n_complete_groups = len(complete_groups)
    expected_rows_from_complete_groups = n_complete_groups * len(source_param_ids)
    print(
        f"  > {n_complete_groups:,} same station/day group(s) have all "
        f"{len(source_param_ids)} source parameters"
    )

    incomplete_cases = grouped_sources[grouped_sources["n_available"] < len(source_param_ids)].copy()
    if not incomplete_cases.empty:
        incomplete_cases["missing_source_params"] = incomplete_cases["available_source_params"].map(
            lambda ids: sorted(expected_ids - set(ids))
        )
        incomplete_cases["target_param_id"] = target_param_id
        incomplete_cases["expected_source_params"] = [source_param_ids] * len(incomplete_cases)
        incomplete_cases["source_ops"] = [source_ops] * len(incomplete_cases)
        print(
            f"  ! {len(incomplete_cases)} incomplete case(s): "
            f"not all source combinations present for the same station/day"
        )
    else:
        print("  > All station/day groups contain at least one row for each source parameter")

    if n_complete_groups == 0:
        print(
            "  ! No complete same-day groups found: no aggregated rows were added "
            "because substances are not measured on the same station/day"
        )
        print_data_summary(
            "Output",
            summarize_dataframe(
                df,
                combination_cols=compression_combination_cols,
                combination_label=compression_combination_label,
            ),
            combination_label=compression_combination_label,
        )
        print_row_change(
            rows_before,
            len(df),
            reason=f"no complete same-day groups for target {target_param_id}",
        )
        return df.copy(), incomplete_cases, pd.DataFrame()

    complete_group_keys = complete_groups[group_cols].copy()
    df_sub_complete = df_sub.merge(complete_group_keys, on=group_cols, how="inner")
    extra_rows_in_complete_groups = len(df_sub_complete) - expected_rows_from_complete_groups

    unit_counts_by_group = (
        df_sub_complete.groupby(group_cols, dropna=False)[COL_UNIT]
        .nunique(dropna=True)
        .reset_index(name="unit_count")
    )
    groups_with_multiple_units = int(unit_counts_by_group["unit_count"].gt(1).sum())

    print(
        f"  > Complete groups contain {expected_rows_from_complete_groups:,} "
        "required source row(s) "
        f"({n_complete_groups:,} groups x {len(source_param_ids)} parameters)"
    )
    if extra_rows_in_complete_groups > 0:
        print(
            f"  > Plus {extra_rows_in_complete_groups:,} additional duplicate source row(s) "
            "within those complete groups"
        )

    if unit_source_param is None and groups_with_multiple_units > 0:
        print(
            f"  ! {groups_with_multiple_units:,} complete group(s) contain multiple units "
            "across source parameters. Set unit_source_param_id to choose which source "
            "parameter defines the output unit."
        )
    elif unit_source_param is not None:
        print(
            f"  > Output unit will be taken from source parameter {unit_source_param}"
        )

        selected_unit_subset = df_sub_complete[
            df_sub_complete[COL_PARAMETER].astype(str).eq(unit_source_param)
        ].copy()
        selected_unit_counts = (
            selected_unit_subset.groupby(group_cols, dropna=False)[COL_UNIT]
            .nunique(dropna=True)
            .reset_index(name="selected_unit_count")
        )
        selected_groups_with_multiple_units = int(
            selected_unit_counts["selected_unit_count"].gt(1).sum()
        )
        if selected_groups_with_multiple_units > 0:
            print(
                f"  ! {selected_groups_with_multiple_units:,} complete group(s) still have "
                f"multiple units for selected source parameter {unit_source_param}. "
                "Output unit may be empty for those groups."
            )

        df_sub_complete["__selected_param_unit"] = df_sub_complete[COL_UNIT].where(
            df_sub_complete[COL_PARAMETER].astype(str).eq(unit_source_param)
        )

    lq_conflict_records = []
    aquocode_conflict_records = []
    for group_key, group_df in df_sub_complete.groupby(group_cols, dropna=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)

        lq_values = group_df[COL_LQ].dropna().tolist()
        unique_lq = list(dict.fromkeys(lq_values))

        if len(unique_lq) > 1:
            record = dict(zip(group_cols, group_key))
            record.update(
                {
                    "target_param_id": target_param_id,
                    "lq_values_found": unique_lq,
                    "source_rows_in_group": len(group_df),
                }
            )
            lq_conflict_records.append(record)

        aquocode_values = aggregate_aquocode_list(group_df[COL_AQUOCODE])
        if len(aquocode_values) > 1:
            record = dict(zip(group_cols, group_key))
            record.update(
                {
                    "target_param_id": target_param_id,
                    "aquocodes_found": aquocode_values,
                    "aquocode_kept": select_highest_aquocode(group_df[COL_AQUOCODE]),
                    "source_rows_in_group": len(group_df),
                }
            )
            aquocode_conflict_records.append(record)

    lq_conflicts = pd.DataFrame(lq_conflict_records)
    if not lq_conflicts.empty:
        print(
            f"  ! {len(lq_conflicts)} case(s) with conflicting "
            f"'{COL_LQ}' symbols within a group"
        )
        print("    Tie-break rule: '<' is preferred over '=' when both are present")
    else:
        print("  > LQ symbols are consistent within complete groups")

    aquocode_conflicts = pd.DataFrame(aquocode_conflict_records)
    if not aquocode_conflicts.empty:
        print(
            f"  ! {len(aquocode_conflicts)} case(s) with different "
            f"'{COL_AQUOCODE}' values within a group"
        )
        print("    Tie-break rule: the highest aquocode among the sources is kept")
        for record in aquocode_conflict_records:
            group_desc = ", ".join(f"{col}={record[col]}" for col in group_cols)
            print(
                f"    - {group_desc} | found {record['aquocodes_found']} "
                f"-> kept {record['aquocode_kept']}"
            )
    else:
        print(f"  > '{COL_AQUOCODE}' values are consistent within complete groups")

    df_sub_complete["__op_sign"] = df_sub_complete[COL_PARAMETER].astype(str).map(sign_map)

    agg_dict: dict[str, tuple[str, object]] = {}
    signed_cols: dict[str, str] = {}

    for col in sum_cols:
        safe_col = col.replace(" ", "_")
        signed_col = f"__signed_{safe_col}"
        df_sub_complete[signed_col] = (
            pd.to_numeric(df_sub_complete[col], errors="coerce")
            * df_sub_complete["__op_sign"]
        )
        agg_dict[signed_col] = (signed_col, lambda s: s.sum(min_count=1))
        signed_cols[signed_col] = col

    aquocode_list_col = f"{COL_AQUOCODE}_list"
    lq_list_col = f"{COL_LQ}_list"
    aquocode_list_safe = aquocode_list_col.replace(" ", "_")
    lq_list_safe = lq_list_col.replace(" ", "_")

    agg_dict[COL_AQUOCODE] = (COL_AQUOCODE, select_highest_aquocode)
    agg_dict[aquocode_list_safe] = (COL_AQUOCODE, aggregate_aquocode_list)
    agg_dict[COL_LQ] = (COL_LQ, select_preferred_lq_symbol)
    agg_dict[lq_list_safe] = (COL_LQ, aggregate_lq_list)

    scalar_plus_list_cols = [
        COL_FRACTION,
        COL_CONVERSION,
        COL_RAW_UNIT_CODE,
        "grootheid_code",
        "hoedanigheid_code",
    ]
    generated_list_cols: dict[str, str] = {
        aquocode_list_safe: aquocode_list_col,
        lq_list_safe: lq_list_col,
    }
    for col in scalar_plus_list_cols:
        if col in df_sub_complete.columns:
            list_col = f"{col}_list"
            list_col_safe = list_col.replace(" ", "_")
            agg_dict[col] = (col, select_unique_or_empty)
            agg_dict[list_col_safe] = (col, aggregate_unique_values)
            generated_list_cols[list_col_safe] = list_col

    if COL_UNIT in df_sub_complete.columns:
        unit_series_col = "__selected_param_unit" if unit_source_param is not None else COL_UNIT
        unit_list_col = f"{COL_UNIT}_list"
        unit_list_col_safe = unit_list_col.replace(" ", "_")
        agg_dict[COL_UNIT] = (unit_series_col, select_unique_or_empty)
        agg_dict[unit_list_col_safe] = (unit_series_col, aggregate_unique_values)
        generated_list_cols[unit_list_col_safe] = unit_list_col

    parameter_list_col = f"{COL_PARAMETER}_list"
    parameter_list_col_safe = parameter_list_col.replace(" ", "_")
    agg_dict[parameter_list_col_safe] = (COL_PARAMETER, aggregate_unique_values)
    generated_list_cols[parameter_list_col_safe] = parameter_list_col

    for col in list_cols:
        safe_name = col.replace(" ", "_")
        agg_dict[safe_name] = (col, lambda s: s.dropna().tolist())

    compressed = (
        df_sub_complete.groupby(group_cols, dropna=False)
        .agg(**agg_dict)
        .reset_index()
    )

    rename_map = {col.replace(" ", "_"): col for col in list_cols}
    rename_map.update(signed_cols)
    rename_map.update(generated_list_cols)
    compressed = compressed.rename(columns=rename_map)
    compressed[COL_PARAMETER] = target_param_id

    col_order = [c for c in df.columns if c in compressed.columns]
    extra_cols = list(generated_list_cols.values())
    col_order.extend([c for c in extra_cols if c in compressed.columns and c not in col_order])
    compressed = compressed[col_order]

    print(
        f"  > {len(compressed):,} aggregated row(s) created "
        "(one row per complete station/day group)"
    )

    if remove_source_rows:
        source_subset = df[mask].copy()
        other_subset = df[~mask].copy()
        source_marked = source_subset.merge(
            complete_group_keys.assign(_eligible=1),
            on=group_cols,
            how="left",
        )
        removed_count = int(source_marked["_eligible"].eq(1).sum())
        source_kept = source_marked[source_marked["_eligible"].isna()].drop(columns="_eligible")
        df_result = pd.concat([other_subset, source_kept], ignore_index=True)
        print(
            f"  > {removed_count:,} source rows removed "
            "(only rows in complete same-day groups)"
        )
    else:
        df_result = df.copy()
        print(f"  > Source rows kept (aggregated rows will be appended)")

    df_result = pd.concat([df_result, compressed], ignore_index=True)

    print_data_summary(
        "Output",
        summarize_dataframe(
            df_result,
            combination_cols=compression_combination_cols,
            combination_label=compression_combination_label,
        ),
        combination_label=compression_combination_label,
    )

    print_row_change(
        rows_before,
        len(df_result),
        reason=f"aggregated source combinations into target {target_param_id}",
    )

    return df_result, incomplete_cases, lq_conflicts


def sort_by_station_parameter_date(df: pd.DataFrame) -> pd.DataFrame:
    """Sort harmonized data by station, parameter, and date."""
    print_step_header("Sort output", step=8)
    isc_combination_cols = [COL_PARAMETER, COL_FRACTION, COL_UNIT]
    isc_combination_label = "ISC combinations"

    sort_cols = [COL_STATION, COL_PARAMETER, COL_DATE]
    missing_cols = [c for c in sort_cols if c not in df.columns]
    if missing_cols:
        raise KeyError(f"Missing required columns: {missing_cols}")

    print_data_summary(
        "Input",
        summarize_dataframe(
            df,
            combination_cols=isc_combination_cols,
            combination_label=isc_combination_label,
        ),
        combination_label=isc_combination_label,
    )
    print("  > Sorting by station -> ISC combination -> date")

    df_sorted = df.copy()
    df_sorted["_sort_date"] = pd.to_datetime(
        df_sorted[COL_DATE],
        dayfirst=True,
        errors="coerce",
    )

    return (
        df_sorted.sort_values(
            by=[COL_STATION, COL_PARAMETER, "_sort_date"],
            ascending=[True, True, True],
            na_position="last",
            kind="mergesort",
        )
        .drop(columns="_sort_date")
        .reset_index(drop=True)
    )

    print_data_summary("Output", summarize_dataframe(df_sorted))
    print_row_change(len(df), len(df_sorted), reason="sorting only, no rows dropped")

    return df_sorted


def parse_result_values(values: pd.Series) -> pd.Series:
    """Convert raw result values to numeric, handling comma decimal separators."""
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce")

    normalized = values.astype(str).str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(normalized, errors="coerce")


def format_result_series(values: pd.Series) -> pd.Series:
    """Format numeric results as 4-decimal dot strings; use NV for -999."""
    numeric_vals = parse_result_values(values)
    result = pd.Series(index=values.index, dtype=object)

    nv_mask = numeric_vals.eq(-999)
    result.loc[nv_mask] = "NV"

    num_mask = numeric_vals.notna() & ~nv_mask
    result.loc[num_mask] = numeric_vals.loc[num_mask].map(lambda x: f"{x:.4f}")

    return result


def to_output_text(value) -> str:
    """Convert one output cell to text, including array-like values."""
    # Handle list/tuple/set/array-like values first
    if isinstance(value, (list, tuple, set)):
        return "|".join(to_output_text(v) for v in value)

    # Handle pandas/numpy scalar missing values
    try:
        if pd.isna(value):
            return ""
    except Exception:
        # Some array-like objects make pd.isna return an array
        pass

    text = str(value).strip()
    if text.lower() in {"nan", "none", "<na>"}:
        return ""
    return text


def standardize_output_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all output columns are object strings (numbers and labels coexist)."""
    missing = [c for c in OUTPUT_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    out = df.loc[:, OUTPUT_COLUMNS].copy()
    for col in OUTPUT_COLUMNS:
        out[col] = out[col].map(to_output_text).astype(object)

    return out


def format_result_values(
    df: pd.DataFrame,
    result_col: str = COL_RESULT,
    aquo_col: str = COL_AQUOCODE,
) -> pd.DataFrame:
    """Format numeric results to 4 decimals and set NV for aquocode 99."""
    print_step_header("Format result values", step=9)
    isc_combination_cols = [COL_PARAMETER, COL_FRACTION, COL_UNIT]
    isc_combination_label = "ISC combinations"

    out = df.copy()

    if aquo_col not in out.columns:
        raise KeyError(f"Missing required column: {aquo_col}")
    if result_col not in out.columns:
        raise KeyError(f"Missing required column: {result_col}")

    print_data_summary(
        "Input",
        summarize_dataframe(
            out,
            combination_cols=isc_combination_cols,
            combination_label=isc_combination_label,
        ),
        combination_label=isc_combination_label,
    )

    numeric_vals = parse_result_values(out[result_col])
    out[result_col] = format_result_series(out[result_col])

    mask_99 = pd.to_numeric(out[aquo_col], errors="coerce").eq(99)
    out.loc[mask_99, result_col] = "NV"
    out[result_col] = out[result_col].astype(object)

    n_formatted = int((numeric_vals.notna() & ~numeric_vals.eq(-999)).sum())
    n_nv = int(mask_99.sum())
    print(f"  > {n_formatted:,} numeric results formatted to 4 decimals")
    print(f"  > {n_nv:,} results set to 'NV' (aquocode 99)")
    print_data_summary(
        "Output",
        summarize_dataframe(
            out,
            combination_cols=isc_combination_cols,
            combination_label=isc_combination_label,
        ),
        combination_label=isc_combination_label,
    )
    print_row_change(len(df), len(out), reason="formatting only, no rows dropped")

    return out


def select_output_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the seven Dutch ISC output columns."""
    print_step_header("Select output columns", step=10)
    isc_combination_cols = [COL_PARAMETER, COL_FRACTION, COL_UNIT]
    isc_combination_label = "ISC combinations"

    missing = [c for c in OUTPUT_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    print_data_summary(
        "Input",
        summarize_dataframe(
            df,
            combination_cols=isc_combination_cols,
            combination_label=isc_combination_label,
        ),
        combination_label=isc_combination_label,
    )
    print(f"  > Keeping {len(OUTPUT_COLUMNS)} Dutch output columns")

    result = df.loc[:, OUTPUT_COLUMNS].copy()
    print_data_summary(
        "Output",
        summarize_dataframe(
            result,
            combination_cols=isc_combination_cols,
            combination_label=isc_combination_label,
        ),
        combination_label=isc_combination_label,
    )
    print_row_change(len(df), len(result), reason="column selection only, no rows dropped")

    return result


def create_not_measured_global_rows(
    not_measured_mapping: pd.DataFrame,
    reference_output: pd.DataFrame,
    default_station: str = "",
    default_fraction: str = "",
    default_date: str = "",
    *,
    verbose: bool = True,
) -> pd.DataFrame:
    """Build global NM rows for parameters flagged in the mapping."""
    required_map_cols = [COL_PARAMETER, COL_UNIT]
    missing_map = [c for c in required_map_cols if c not in not_measured_mapping.columns]
    if missing_map:
        raise KeyError(f"Missing columns in not_measured_mapping: {missing_map}")

    missing_target = [c for c in OUTPUT_COLUMNS if c not in reference_output.columns]
    if missing_target:
        raise KeyError(f"Missing columns in reference_output: {missing_target}")

    nm_mapping = (
        not_measured_mapping[[COL_PARAMETER, COL_UNIT]]
        .dropna(subset=[COL_PARAMETER])
        .drop_duplicates()
        .copy()
    )

    stations = (
        reference_output[COL_STATION]
        .astype("string")
        .str.strip()
        .dropna()
    )
    stations = stations[stations.ne("")].drop_duplicates().tolist()

    if stations:
        station_table = pd.DataFrame({COL_STATION: stations})
        nm_table = nm_mapping.merge(station_table, how="cross")
    else:
        nm_table = nm_mapping.copy()
        nm_table[COL_STATION] = default_station

    nm_table[COL_FRACTION] = default_fraction
    nm_table[COL_DATE] = default_date
    nm_table[COL_LQ] = "="
    nm_table[COL_RESULT] = "NM"

    if verbose:
        print_step_header("Create not-measured (NM) rows", step=13)
        print_not_measured_mapping_summary(not_measured_mapping)
        print(
            f"  > Expanded to {len(nm_table):,} NM rows across {len(stations):,} station(s)"
        )
        print(f"  > Each row has Resultaat = 'NM' with empty fraction and date")

    return nm_table[OUTPUT_COLUMNS]


def create_not_measured_local_rows(
    reference_output: pd.DataFrame,
    measured_mapping: pd.DataFrame,
    default_date: str = "",
    *,
    verbose: bool = True,
) -> pd.DataFrame:
    """Build local NM rows for missing ISC combinations per station."""
    missing_target = [c for c in OUTPUT_COLUMNS if c not in reference_output.columns]
    if missing_target:
        raise KeyError(f"Missing columns in reference_output: {missing_target}")

    if COL_STATION not in reference_output.columns:
        raise KeyError(f"Missing required column in reference_output: {COL_STATION}")

    # measured_mapping only maps parameter/unit (fraction comes from a separate
    # mapping table), so it usually lacks COL_FRACTION. Fall back to deriving the
    # expected combinations from the reference output itself (union across all
    # stations) in that case.
    if all(col in measured_mapping.columns for col in ISC_COMBINATION_COLS):
        expected_source = measured_mapping
        if verbose:
            print("  Expected ISC combinations source: measured parameter mapping")
    else:
        expected_source = reference_output
        if verbose:
            print(
                f"  Expected ISC combinations source: every "
                f"{'+'.join(ISC_COMBINATION_COLS)} combination seen at any "
                "station in this dataset is treated as expected at every station."
            )

    expected_combos = normalize_isc_combination_columns(expected_source)
    expected_set = isc_combination_tuples(expected_combos)

    if verbose:
        print(f"  Expected ISC combinations: {len(expected_set):,}")

    stations = (
        reference_output[COL_STATION]
        .astype("string")
        .str.strip()
        .dropna()
    )
    stations = stations[stations.ne("")].drop_duplicates().tolist()

    local_rows: list[dict[str, str]] = []

    for station in stations:
        station_data = reference_output[reference_output[COL_STATION].astype("string").str.strip() == station]
        measured_set = isc_combination_tuples(station_data) if len(station_data) else set()
        missing_set = sorted(expected_set - measured_set)

        if verbose:
            print(f"\n  Station: {station}")
            print(
                f"  > Missing ISC combinations at station: {len(missing_set):,} / {len(expected_set):,}"
            )
            if missing_set:
                print(f"  Not measured at this station ({len(missing_set):,}):")
                for combo in missing_set:
                    print(f"    - {format_isc_combination_tuple(combo)}")
            else:
                print("  > All expected ISC combinations are present at this station")

        for combo in missing_set:
            combo_dict = dict(zip(ISC_COMBINATION_COLS, combo))
            local_rows.append(
                {
                    COL_STATION: station,
                    COL_DATE: default_date,
                    COL_FRACTION: combo_dict[COL_FRACTION],
                    COL_PARAMETER: combo_dict[COL_PARAMETER],
                    COL_LQ: "=",
                    COL_RESULT: "NM",
                    COL_UNIT: combo_dict[COL_UNIT],
                }
            )

    local_nm = pd.DataFrame(local_rows, columns=OUTPUT_COLUMNS)

    if verbose and local_nm.empty:
        print("  > No local missing combinations found; no local NM rows created")

    return local_nm


def create_am_biological_quality_rows(
    am_classifications: dict[str, dict[str, str]],
    am_mapping: pd.DataFrame,
    reference_output: pd.DataFrame,
    *,
    default_date: str = "",
    verbose: bool = True,
) -> pd.DataFrame:
    """Build manually-added (AM) biological quality rows and append them to reference_output.

    ``am_classifications`` maps station -> {parameter_id: classification_value},
    e.g. {"NL89_SASVGT": {"IBGN": "Goed (Bon)", "IBD": "Goed (Bon)"}}.
    ``am_mapping`` is the subset of the parameter mapping table flagged
    ``reported == "AM"``, used only to look up the unit for each parameter ID.
    ``reference_output`` is the dataframe to append the AM rows to (e.g. the
    harmonized output combined with chlorophyll).

    Returns ``reference_output`` with the AM rows appended.
    """
    required_cols = [COL_PARAMETER, COL_UNIT]
    missing_cols = [c for c in required_cols if c not in am_mapping.columns]
    if missing_cols:
        raise KeyError(f"Missing columns in am_mapping: {missing_cols}")

    if verbose:
        print_step_header("Add manually-added (AM) biological quality rows")
        print_data_summary(
            "Input",
            summarize_dataframe(
                reference_output,
                combination_cols=ISC_COMBINATION_COLS,
                combination_label=ISC_COMBINATION_LABEL,
            ),
            combination_label=ISC_COMBINATION_LABEL,
        )

    unit_lookup = (
        am_mapping[[COL_PARAMETER, COL_UNIT]]
        .dropna(subset=[COL_PARAMETER])
        .drop_duplicates(subset=[COL_PARAMETER])
        .set_index(COL_PARAMETER)[COL_UNIT]
        .to_dict()
    )

    rows = []
    unknown_parameters = set()
    for station, param_values in am_classifications.items():
        for param_id, classification in param_values.items():
            if param_id not in unit_lookup:
                unknown_parameters.add(param_id)
                continue
            rows.append(
                {
                    COL_STATION: station,
                    COL_DATE: default_date,
                    COL_FRACTION: "",
                    COL_PARAMETER: param_id,
                    COL_LQ: "",
                    COL_RESULT: classification,
                    COL_UNIT: unit_lookup[param_id],
                }
            )

    am_rows = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    combined_output = pd.concat([reference_output, am_rows], ignore_index=True)

    if verbose:
        print(f"  AM parameters available in mapping: {sorted(unit_lookup.keys())}")
        if unknown_parameters:
            print(
                f"  ! {len(unknown_parameters)} parameter ID(s) in am_classifications "
                f"not found in am_mapping (reported = AM), skipped: "
                f"{sorted(unknown_parameters)}"
            )
        print(f"  > {len(am_rows):,} AM row(s) created from {len(am_classifications):,} station(s)")
        for _, row in am_rows.iterrows():
            print(
                f"    - {row[COL_STATION]} | {row[COL_PARAMETER]} = {row[COL_RESULT]}"
            )
        print_data_summary(
            "Output",
            summarize_dataframe(
                combined_output,
                combination_cols=ISC_COMBINATION_COLS,
                combination_label=ISC_COMBINATION_LABEL,
            ),
            combination_label=ISC_COMBINATION_LABEL,
        )
        print_row_change(
            len(reference_output),
            len(combined_output),
            reason="AM biological quality rows appended",
        )

    return combined_output


def set_nv_for_parameter_ids(
    df: pd.DataFrame,
    parameter_ids: list[str | int] | None,
    *,
    parameter_col: str = COL_PARAMETER,
    result_col: str = COL_RESULT,
) -> pd.DataFrame:
    """Set Resultaat to NV for rows whose parameter ID is in parameter_ids."""
    if not parameter_ids:
        return df

    if parameter_col not in df.columns:
        raise KeyError(f"Missing required column: {parameter_col}")
    if result_col not in df.columns:
        raise KeyError(f"Missing required column: {result_col}")

    normalized_ids = {str(value).strip() for value in parameter_ids if pd.notna(value)}
    if not normalized_ids:
        return df

    out = df.copy()
    param_values = out[parameter_col].astype("string").str.strip()
    mask = param_values.isin(normalized_ids)
    out.loc[mask, result_col] = "NV"

    print_step_header("Apply forced NV parameter IDs")
    print(f"  > Configured parameter IDs: {sorted(normalized_ids)}")
    print(f"  > {int(mask.sum()):,} row(s) set to 'NV'")

    return out


def transform_chlorophyll_to_isc_format(
    chlorophyll_raw: pd.DataFrame,
    location_lookup: pd.DataFrame,
    parameter_info: pd.DataFrame,
) -> pd.DataFrame:
    """Transform RWS chlorophyll-a export to Dutch ISC output columns."""
    cols = [
        "ComponentName",
        "UHoedanigheid",
        "ResultType",
        "UMeetpunt",
        "ResultText",
        "ResultUMeetonzekerheid",
        "ResultValue",
        "UGeplandeDatum",
    ]
    df = chlorophyll_raw[cols].copy()

    meetpunt = df["UMeetpunt"].unique()
    location_code = location_lookup[location_lookup["rwsformat"] == meetpunt[0]]
    df[COL_STATION] = df["UMeetpunt"].replace(
        meetpunt, location_code["iscformat"].values[0]
    )
    df[COL_FRACTION] = df["UHoedanigheid"].replace("NVT", "EB")
    df[COL_DATE] = pd.to_datetime(
        df["UGeplandeDatum"], format="mixed"
    ).dt.strftime("%d/%m/%Y")
    df[COL_LQ] = df["ResultText"].str.contains("<", regex=True).map(
        {True: "<", False: "="}
    )
    df[COL_RESULT] = format_result_series(df["ResultValue"])
    df[COL_PARAMETER] = str(parameter_info["uid"].values[0])
    # Normalize common mojibake so chlorophyll rows match existing ISC unit values.
    df[COL_UNIT] = "\u00b5g/L"
    df[COL_UNIT] = (
        df[COL_UNIT]
        .astype("string")
        .str.replace("Âµ", "\u00b5", regex=False)
        .str.strip()
    )

    return df[OUTPUT_COLUMNS]


def load_and_filter_chlorophyll_data(
    chlorophyll_path: Path,
    target_year: int,
) -> pd.DataFrame:
    """Load and transform chlorophyll data, filtered to the target year."""
    schaar_raw = pd.read_excel(chlorophyll_path, sheet_name="SCHAARVODDL CHLfa")
    sasvgt_raw = pd.read_excel(chlorophyll_path, sheet_name="SASVGT CHLfa")

    location_lookup = pd.DataFrame(
        {
            "iscformat": ["NL89_SASVGT", "NL89_SCHAARVODDL"],
            "rwsformat": ["SASVGT", "SCHAARVODDL"],
        }
    )

    parameter_info = pd.DataFrame(
        [
            {
                "uid": 1439,
                "PARAMETRE": "Chlorophylle a",
                "n° CAS nr": "479-61-8",
                "Unieke identificatie gemeten parameter": "Chlorofyl a",
                "Unieke eenheidsidentificatie": "\u00b5g/L",
                "ComponentName": "CHLFa",
            }
        ]
    )

    schaar_output = transform_chlorophyll_to_isc_format(
        schaar_raw, location_lookup, parameter_info
    )
    sasvgt_output = transform_chlorophyll_to_isc_format(
        sasvgt_raw, location_lookup, parameter_info
    )
    chlorophyll_all = pd.concat([schaar_output, sasvgt_output], ignore_index=True)

    chlorophyll_year = chlorophyll_all[
        pd.to_datetime(chlorophyll_all[COL_DATE], dayfirst=True).dt.year == target_year
    ]

    print_step_header("Load chlorophyll-a data", step=11)
    print(f"  > SCHAARVODDL rows loaded: {len(schaar_output):,}")
    print(f"  > SASVGT rows loaded: {len(sasvgt_output):,}")
    print(f"  > Total before year filter: {len(chlorophyll_all):,}")
    print(f"  > Rows for {target_year}: {len(chlorophyll_year):,}")

    if len(chlorophyll_year) == 0:
        print(f"  ! No chlorophyll data found for {target_year}")
    else:
        print_data_summary(
            "Output",
            summarize_dataframe(
                chlorophyll_year,
                combination_cols=ISC_COMBINATION_COLS,
                combination_label=ISC_COMBINATION_LABEL,
            ),
            combination_label=ISC_COMBINATION_LABEL,
        )

    return chlorophyll_year


def combine_harmonized_and_chlorophyll(
    harmonized_output: pd.DataFrame,
    chlorophyll_year: pd.DataFrame,
) -> pd.DataFrame:
    """Append chlorophyll rows to the harmonized measurement output."""
    print_step_header("Combine harmonized data with chlorophyll", step=12)
    print_data_summary(
        "Harmonized measurements",
        summarize_dataframe(
            harmonized_output,
            combination_cols=ISC_COMBINATION_COLS,
            combination_label=ISC_COMBINATION_LABEL,
        ),
        combination_label=ISC_COMBINATION_LABEL,
    )
    print_data_summary(
        "Chlorophyll",
        summarize_dataframe(
            chlorophyll_year,
            combination_cols=ISC_COMBINATION_COLS,
            combination_label=ISC_COMBINATION_LABEL,
        ),
        combination_label=ISC_COMBINATION_LABEL,
    )

    output_with_chlorophyll = pd.concat(
        [harmonized_output, chlorophyll_year],
        ignore_index=True,
    )
    print_data_summary(
        "Combined",
        summarize_dataframe(
            output_with_chlorophyll,
            combination_cols=ISC_COMBINATION_COLS,
            combination_label=ISC_COMBINATION_LABEL,
        ),
        combination_label=ISC_COMBINATION_LABEL,
    )
    print_row_change(
        len(harmonized_output),
        len(output_with_chlorophyll),
        reason="chlorophyll rows appended",
    )

    return output_with_chlorophyll


def create_not_measured_and_finalize(
    output_with_chlorophyll: pd.DataFrame,
    not_measured_mapping: pd.DataFrame,
    *,
    measured_mapping: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Create global + local NM rows and finalize output.

    Note: forced-NV parameter IDs (SNV) are applied earlier in the pipeline,
    right after ``format_result_values``, alongside the aquocode-99 NV logic.
    """
    global_not_measured_rows = create_not_measured_global_rows(
        not_measured_mapping,
        output_with_chlorophyll,
        verbose=True,
    )

    if measured_mapping is not None:
        print_step_header("Missing ISC combinations per station (local NM)", step=14)
        local_not_measured_rows = create_not_measured_local_rows(
            output_with_chlorophyll,
            measured_mapping,
            verbose=True,
        )
    else:
        local_not_measured_rows = pd.DataFrame(columns=OUTPUT_COLUMNS)

    not_measured_rows = pd.concat(
        [global_not_measured_rows, local_not_measured_rows],
        ignore_index=True,
    )
    print(
        f"\n  > {len(global_not_measured_rows):,} global NM rows + "
        f"{len(local_not_measured_rows):,} local NM rows = "
        f"{len(not_measured_rows):,} total NM rows"
    )

    final_output = pd.concat(
        [output_with_chlorophyll, not_measured_rows],
        ignore_index=True,
    )

    final_output = standardize_output_dtypes(final_output)

    print_step_header("Final dataset ready", step=15)
    print_data_summary(
        "Final dataset",
        summarize_dataframe(
            final_output,
            combination_cols=ISC_COMBINATION_COLS,
            combination_label=ISC_COMBINATION_LABEL,
        ),
        combination_label=ISC_COMBINATION_LABEL,
    )
    print(f"  > Measured + chlorophyll rows: {len(output_with_chlorophyll):,}")
    print(f"  > NM rows appended: {len(not_measured_rows):,}")
    print(
        "  > Per-station missing combinations were already reported and filled as "
        "local NM rows above"
    )

    return final_output


def export_final_output(
    final_output: pd.DataFrame,
    output_base_path: Path,
    *,
    sheet_name: str = "harmonized",
) -> tuple[Path, Path]:
    """Save final output as semicolon-separated CSV and Excel workbook."""
    csv_path = output_base_path.with_suffix(".csv")
    xlsx_path = output_base_path.with_suffix(".xlsx")

    print_step_header("Export output files", step=17)

    output = standardize_output_dtypes(final_output)

    output.to_csv(csv_path, index=False, sep=";", encoding="utf-8-sig")
    print(f"  > Saved CSV: {csv_path}")

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        output.to_excel(writer, index=False, sheet_name=sheet_name)
        worksheet = writer.sheets[sheet_name]
        for row_idx in range(2, len(output) + 2):
            for col_idx in range(1, len(output.columns) + 1):
                worksheet.cell(row=row_idx, column=col_idx).number_format = "@"

    print(f"  > Saved Excel: {xlsx_path}")
    print("  > All output columns exported as text (supports numbers and labels like NV/NM)")

    return csv_path, xlsx_path


def run_harmonization_pipeline(
    target_year: int,
    repo_root: Path | None = None,
    nv_parameter_ids: list[str | int] | None = None,
    am_classifications: dict[str, dict[str, str]] | None = None,
) -> pd.DataFrame:
    """Run the full harmonization pipeline and return the final output dataframe."""
    if repo_root is None:
        repo_root = get_repo_root()

    data_dir = repo_root / "voorbeeld" / "isc_2023-2025"
    mapping_dir = repo_root / "mappings"

    print_step_header(f"ISC harmonization pipeline - year {target_year}")
    print(f"  Data directory: {data_dir}")
    print(f"  Mapping directory: {mapping_dir}")

    raw_measurements = pd.read_excel(
        data_dir / f"ISC_{target_year}.xlsx",
        sheet_name=str(target_year),
    )
    location_mapping = pd.read_excel(mapping_dir / "locations-mapped.xlsx")
    parameter_mapping = pd.read_excel(
        mapping_dir / "parameter_mapping_final.xlsx",
        sheet_name="mapping",
    )
    fraction_mapping = pd.read_excel(mapping_dir / "hoedanigheid_mapped.xlsx")

    print_loaded_inputs(
        raw_measurements,
        location_mapping,
        parameter_mapping,
        fraction_mapping,
    )

    measured_mapping, not_measured_mapping, am_mapping, sk_mapping, snv_mapping = split_measured_and_not_measured_parameters(
        parameter_mapping
    )

    measurements = add_parameter_ids_from_mapping(raw_measurements, measured_mapping)
    measurements = add_station_ids_from_mapping(measurements, location_mapping)
    measurements = add_fraction_labels_from_mapping(measurements, fraction_mapping)

    filtered = apply_isc_measurement_filters(measurements)
    filtered, _removed = keep_lowest_aquocode_per_case(filtered)

    harmonized = build_harmonized_output(filtered)

    harmonized_compressed, _, _ = aggregate_compound_parameters(
        harmonized,
        source_param_ids=["1283", "1629", "1630"],
        source_ops=["+", "+", "+"],
        source_fractions=["EB", "EB", "EB"],
        target_param_id="1774",
        remove_source_rows=False,
    )
    harmonized_compressed, _, _ = aggregate_compound_parameters(
        harmonized_compressed,
        source_param_ids=["1103", "1181", "1173", "1207"],
        source_ops=["+", "+", "+", "+"],
        source_fractions=["EB", "EB", "EB", "EB"],
        target_param_id="5534",
        remove_source_rows=False,
    )
    harmonized_compressed, _, _ = aggregate_compound_parameters(
        harmonized_compressed,
        source_param_ids=["6561a", "6561b"],
        source_ops=["+", "+"],
        source_fractions=["EB", "EB"],
        target_param_id="6561",
        remove_source_rows=True,
    )

    harmonized_for_report = sort_by_station_parameter_date(harmonized_compressed)
    formatted_output = format_result_values(harmonized_for_report)
    formatted_output = set_nv_for_parameter_ids(
        formatted_output,
        get_snv_parameter_ids(snv_mapping) + list(nv_parameter_ids or []),
    )
    harmonized_output = select_output_columns(formatted_output)

    chlorophyll_path = data_dir / "SCHAARVODDL + SASVGT_CHLfa_2023-2025.xlsx"
    chlorophyll_year = load_and_filter_chlorophyll_data(chlorophyll_path, target_year)

    output_with_chlorophyll = combine_harmonized_and_chlorophyll(
        harmonized_output,
        chlorophyll_year,
    )

    if am_classifications:
        output_with_chlorophyll = create_am_biological_quality_rows(
            am_classifications,
            am_mapping,
            output_with_chlorophyll,
            default_date=f"31/12/{target_year}",
        )

    final_output = create_not_measured_and_finalize(
        output_with_chlorophyll,
        not_measured_mapping,
        measured_mapping=measured_mapping,
    )

    export_final_output(
        final_output,
        data_dir / f"ISC_{target_year}_harmonized",
        sheet_name=str(target_year),
    )

    return final_output
