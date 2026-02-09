#%% mapping of manually checked parameter table to the aquo vompartiment, kwaliteitscode, eenheid tables to create the final mapping table to be used in 03_map_data.py
import pandas as pd
import os
from pathlib import Path

p=Path(os.getcwd())

compartiment = pd.read_csv(Path.joinpath(p.parent, 'AQUO/Compartiment.csv'), sep = ';')
kwaliteitscode = pd.read_csv(Path.joinpath(p.parent, 'AQUO/Kwaliteitscode.csv'), sep = ';')
eenheid = pd.read_csv(Path.joinpath(p.parent, 'AQUO/Eenheid.csv'), sep=';')
donar_isc_cas = pd.read_excel(Path.joinpath(p.parent, 'mappings/parameter_manual.xlsx'), sheet_name='donar_isc_cas')
parameter_manual = pd.read_excel(Path.joinpath(p.parent, 'mappings/parameter_manual.xlsx'), sheet_name='manual_match_isc')

# %%
