#%%
import pandas as pd
import os
from pathlib import Path

p=Path(os.getcwd())
donar = pd.read_csv(Path.joinpath(p, 'voorbeeld/isc2024/isc2024.csv'), sep =';')
gevraagd_format = pd.read_excel(Path.joinpath(p, 'voorbeeld/ISC-CIE WGM_Tranfert des données RHME 2024_Sept 2025.xlsx'), sheet_name=None)
aangeleverd_2024 =  pd.read_excel(Path.joinpath(p, 'voorbeeld/ISC-CIE WGM_Oct 2025_NL.xlsx'), sheet_name=None)
aquo = pd.read_csv(Path.joinpath(p, 'AQUO/Parameter.csv'), sep =';')
# %%
# preprocessing, unpacking multiple excel sheets and selecting what is needed for the analysis
donarcols = donar.columns
sheets = gevraagd_format.keys()
sheetsa = aangeleverd_2024.keys()
tables = [k for k in  sheetsa] # lsit of desired cols

meetdata = gevraagd_format[tables[1]] #data
locations = gevraagd_format[tables[2]] # locaties
parameter = gevraagd_format[tables[5]] # parameter
new_header = meetdata.iloc[3]
meetdata = meetdata[4:]                 
meetdata.columns = new_header
# %% location mapping
lsloc=donar['LOCOMS'].drop_duplicates().to_frame()
meetdatalsloc = meetdata['Unieke identiticatie meetpunt'].drop_duplicates().to_frame()

locs= locations[['Identitication unique de la station' , 'Localité']]
locs=locs.groupby(['Identitication unique de la station' , 'Localité']).count().reset_index()
# %% parameter mapping
#gewoon paroms mappen naar de ISC tabel die gegeven is, geeft maar 6 matches, dit is dus niet wat je wil gebruiken
#eerst dan mapping op CAS nummer 
aquo = aquo[aquo['Status'].isin(['Geldig'])]
aquocols = ['CASnummer', 'Codes', 'Omschrijving']
aquo = aquo[aquocols]

paroms = donar['PAROMS'].drop_duplicates().to_frame()
paroms = paroms.rename(columns = {'PAROMS': 'Parameter'})

# %% map DONAR PAROMS naar AQUO CAS nummers
casnummers = paroms.merge(aquo, left_on='Parameter', right_on='Omschrijving', how='inner', validate='one_to_one')
# MAP DONAR with CAS nummers to ISC table
casnummers = casnummers[casnummers['CASnummer'] != 'NVT'] #otherwise not one to one mapping
merged = casnummers.merge(parameter, left_on = 'CASnummer', right_on='n° CAS nr', how = 'inner', validate ='one_to_one')
# %%
up= meetdata['Unieke identificatie gemeten parameter'].drop_duplicates().to_frame()

parameter = parameter.rename(columns={'Identification unique du paramètre mesuré\nCode sandre': 'Unieke identificatie gemeten parameter',
                                      'Unnamed: 3': 'Parameter'})
# upa = parameter.groupby(['Unieke identificatie gemeten parameter', 'Parameter']).count().reset_index()
merged = parameter[['Unieke identificatie gemeten parameter', 'Parameter']].merge(paroms, on = 'Parameter', how='outer', indicator = True)
df_right_anti = merged.query("_merge == 'right_only'")[merged.columns]