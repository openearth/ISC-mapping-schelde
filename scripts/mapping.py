#%%
import pandas as pd
import os
from pathlib import Path

p=Path(os.getcwd())
donar = pd.read_csv(Path.joinpath(p.parent, 'voorbeeld/isc2024/isc2024.csv'), sep =';')
gevraagd_format = pd.read_excel(Path.joinpath(p.parent, 'voorbeeld/ISC-CIE WGM_Tranfert des données RHME 2024_Sept 2025.xlsx'), sheet_name=None)
aangeleverd_2024 =  pd.read_excel(Path.joinpath(p.parent, 'voorbeeld/ISC-CIE WGM_Oct 2025_NL.xlsx'), sheet_name=None)
aquo = pd.read_csv(Path.joinpath(p.parent, 'AQUO/Parameter.csv'), sep =';')
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
#eerst dan mapping op CAS nummer naar ISC daarna DONAR naar de CAS + ICS tabel
aquo = aquo[aquo['Status'].isin(['Geldig'])]
aquo = aquo.rename(columns={'Omschrijving': 'AQUO_Omschrijving'})
aquocols = ['CASnummer', 
            'Codes', 
            'AQUO_Omschrijving'
            ]
casnummers = aquo[aquocols]

paroms = donar[['PAROMS', 'HDH']].drop_duplicates()
paroms = paroms.rename(columns = {'PAROMS': 'DONAR_Parameter'})

# %% # MAP ISC table to CAS nummers
# casnummers = casnummers[casnummers['CASnummer'] != 'NVT'] #otherwise not one to one mapping
parameter = parameter.rename(columns={'Identification unique du paramètre mesuré\nCode sandre': 'Unieke identificatie gemeten parameter',
                                      'Unnamed: 3': 'ISC_Parameter',
                                      'n° CAS nr': 'CASnummer'})
# parameter = parameter[~parameter['CASnummer'].isin(['-',' -'])]
parameter['CASnummer'] = parameter['CASnummer'].str.strip()
cols = ['Unieke identificatie gemeten parameter', 'CASnummer', 'AQUO_Omschrijving', 'ISC_Parameter', 'Identification unique de l\'unité'] 
innerjoin = parameter.merge(casnummers, on = 'CASnummer', how = 'inner') #alle ISC die wel met CASnummers kunnen worden gemapt
innerjoin = innerjoin[cols]

leftjoin = (parameter.merge(casnummers, on='CASnummer',how='left', indicator=True) #Alle ISC die niet met CASnummers kunnen worden gemapt
            .query('_merge == "left_only"')
            .drop('_merge', axis=1))

leftjoin = leftjoin[cols]
print('total parameters =', len(parameter), 
      '\nISC match with CAS numbers=', len(innerjoin), 
      '\n NO match ISC with CAS=', len(leftjoin),
      '\n SUM', len(innerjoin)+ len(leftjoin))
# %%
# Join DONAR met complete ISC mapping met CAS nummers en kijk wat er wel en niet gemapt kan worden van DONAR naar ISC. 
# Hebben we alle variabelen die nodig zijn?
donar_isc_cas = innerjoin.merge(paroms, left_on='AQUO_Omschrijving', right_on='DONAR_Parameter', how='inner') #, validate='one_to_one'
nomatch_donar_isc_cas = (innerjoin.merge(paroms, left_on='AQUO_Omschrijving', right_on='DONAR_Parameter', how = 'left', indicator=True) #Alle ISC die niet met CASnummers kunnen worden gemapt
                        .query('_merge == "left_only"')
                        .drop('_merge', axis=1))

print('total can be mapped from DONAR to ISC =', len(donar_isc_cas), 
      '\n Cannot find match for ISC parameters with DONAR', len(nomatch_donar_isc_cas),
      '\n SUM', len(donar_isc_cas)+ len(nomatch_donar_isc_cas))
# %%
up= meetdata['Unieke identificatie gemeten parameter'].drop_duplicates().to_frame()
# upa = parameter.groupby(['Unieke identificatie gemeten parameter', 'Parameter']).count().reset_index()
