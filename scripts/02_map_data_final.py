#%%
import pandas as pd
import os
from pathlib import Path

p= Path(os.getcwd())
donar = pd.read_csv(Path.joinpath(p.parent, 'voorbeeld/isc2024/isc2024.csv'), sep =';')

donar_isc_cas = pd.read_csv(Path.joinpath(p.parent,'mappings/donar-isc-cas.csv'))
all_locs = pd.read_excel(Path.joinpath(p.parent,'mappings/locations-mapped.xlsx'))
# %%
donar = donar[donar['LOCOMS'].isin(all_locs['LOCOMS'].to_list())] #filter op locaties
donar = donar[donar['KWC'] <= 50] # filter op kwaliteit
# %%
# daggemiddelden berekenen door de location + parameter combinatie 
# mappen naar de parameter mapping
donarmap = donar.merge(donar_isc_cas, left_on='PAROMS', right_on = 'DONAR_Parameter', how='inner')

# Ensure strings and pad TIME to 4 digits (HHMM)
date_str = donarmap["DATUM"].astype(str).str.zfill(8)      # '20240109'
time_str = donarmap["TIJD"].astype(str).str.zfill(4)      # '1250', '0905', '0005'

# Concatenate and parse
donarmap["timestamp"] = pd.to_datetime(date_str + time_str, format="%Y%m%d'%H%M", errors="coerce")
donarmap = donarmap.drop(columns=["DATUM", "TIJD"])

# 1) Remove all characters except digits, +, -, ., e/E
clean = donarmap["WAARDE"].astype(str).str.replace(r"[^0-9eE+\-\.]", "", regex=True)

# 2) Convert to numeric (scientific notation is supported)
donarmap["value"] = pd.to_numeric(clean, errors="coerce")
# %%
donarmap["date"] = donarmap["timestamp"].dt.floor("D")

daily = (
    donarmap
    .groupby(["LOCOMS", "PAROMS", "date"], as_index=False)["value"]
    .mean()
    .rename(columns={"value": "value_daily_mean"})
)
