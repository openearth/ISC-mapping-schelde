#%% FIRST mapping of parameter on ISC, CAS, AQUO and DONAR. Creates initial parameter excel / csv which needs to be manually checked + extended
import pandas as pd
import os
from pathlib import Path

p=Path(os.getcwd())
donar = pd.read_csv(Path.joinpath(p.parent, 'voorbeeld/isc2024/isc2024.csv'), sep =';')
wadar = pd.read_csv(Path.joinpath(p.parent, 'voorbeeld/WADAR/ISC2024/ISC2024.csv'), sep = ';', low_memory = False)
gevraagd_format = pd.read_excel(Path.joinpath(p.parent, 'voorbeeld/ISC-CIE WGM_Tranfert des données RHME 2024_Sept 2025.xlsx'), sheet_name=None)
aangeleverd_2024 =  pd.read_excel(Path.joinpath(p.parent, 'voorbeeld/ISC-CIE WGM_Oct 2025_NL.xlsx'), sheet_name=None)
aquo = pd.read_csv(Path.joinpath(p.parent, 'AQUO/Parameter.csv'), sep =';')
hoedanigheid = pd.read_csv(Path.joinpath(p.parent, 'AQUO/Hoedanigheid.csv'), sep=';')
# %%
# preprocessing, unpacking multiple excel sheets and selecting what is needed for the analysis
wadarcols = wadar.columns
sheets = gevraagd_format.keys()
sheetsa = aangeleverd_2024.keys()
tables = [k for k in  sheetsa] # list of desired cols

meetdata = gevraagd_format[tables[1]] #data
locations = gevraagd_format[tables[2]] # locaties
parameter = gevraagd_format[tables[5]] # parameter
new_header = meetdata.iloc[3]
meetdata = meetdata[4:]                 
meetdata.columns = new_header
meetdata_mapping = meetdata[['Geanalyseerde fractie',
       'Unieke identificatie gemeten parameter',
          'Unieke identificatie van de eenheid']].drop_duplicates()

meetdata_mapping['Geanalyseerde fractie'] = meetdata_mapping['Geanalyseerde fractie'].replace('EB','NVT')
meetdata_mapping['Geanalyseerde fractie'] = meetdata_mapping['Geanalyseerde fractie'].replace('EF','nf')
# %% parameter mapping
#gewoon paroms mappen naar de ISC tabel die gegeven is, geeft maar 6 matches, dit is dus niet wat je wil gebruiken
# PARCODE gebruiken om te mappen naar AQUO
#eerst dan mapping op CAS nummer naar ISC daarna wadar naar de CAS + ICS tabel
aquo = aquo[aquo['Status'].isin(['Geldig'])]
aquo = aquo.rename(columns={'Omschrijving': 'AQUO_Omschrijving',
                            'Codes': 'AQUO_Codes'})
aquocols = ['CASnummer', 
            'AQUO_Codes', 
            'AQUO_Omschrijving'
            ]
casnummers = aquo[aquocols]

# eenheden en de eenheden mapping van DONAR -? ISC lijkt wel anders te zijn dan de eenheden mapping van WADAR -> ISC

#AQUOcode kwaliteit: https://www.aquo.nl/index.php/Id-1e17d9e6-4e0e-4f88-8fe5-c71f6a7931db
# 99: hiaat
# 0: normale waarde (zou 00 moeten zijn)
# 3: Waarde heeft een grotere spreiding dan beschreven
# 90: Afwijkende waarde na validatie goedgekeurd
# 1002: ??? bestaat niet in aquolijst

# voor ISC is er een unieke code bij gebrek aan resultaat -> moet dit verplicht meegegeven worden
# NM : geen meting
# NV : niet gevalideerd
# paroms = wadar[['PAROMS', 'PAR','HDH']].drop_duplicates()
paroms = wadar[['grootheid_code',
                'parameter_code', 
                'hoedanigheid_code']].drop_duplicates()
paroms = paroms.rename(columns = {'parameter_code': 'wadar_PARCode'})

# %% # MAP ISC table to CAS nummers
# casnummers = casnummers[casnummers['CASnummer'] != 'NVT'] #otherwise not one to one mapping
parameter = parameter.rename(columns={'Identification unique du paramètre mesuré\nCode sandre': 'Unieke identificatie gemeten parameter',
                                      'Unnamed: 3': 'ISC_Parameter',
                                      'n° CAS nr': 'CASnummer'})
# parameter = parameter[~parameter['CASnummer'].isin(['-',' -'])]
parameter['CASnummer'] = parameter['CASnummer'].str.strip()
cols = ['Unieke identificatie gemeten parameter', 
        'CASnummer', 
        'AQUO_Codes',
        'AQUO_Omschrijving', 
        'ISC_Parameter', 
        'Geanalyseerde fractie',
       'Unieke identificatie van de eenheid'
        ] 
parameterx = parameter.merge(meetdata_mapping, on='Unieke identificatie gemeten parameter', how = 'outer')
#%%
innerjoin = parameterx.merge(casnummers, on = 'CASnummer', how = 'inner') #alle ISC die wel met CASnummers kunnen worden gemapt
innerjoin = innerjoin[cols]

leftjoin = (parameterx.merge(casnummers, on='CASnummer',how='left', indicator=True) #Alle ISC die niet met CASnummers kunnen worden gemapt
            .query('_merge == "left_only"')
            .drop('_merge', axis=1))

leftjoin = leftjoin[cols]
print('total parameters =', len(parameterx), 
      '\nISC match with CAS numbers=', len(innerjoin), 
      '\n NO match ISC with CAS=', len(leftjoin),
      '\n SUM', len(innerjoin)+ len(leftjoin))

# Join wadar met complete ISC mapping met CAS nummers en kijk wat er wel en niet gemapt kan worden van wadar naar ISC. 
# Hebben we alle variabelen die nodig zijn?
wadar_isc_cas = innerjoin.merge(paroms, left_on='AQUO_Codes', right_on='wadar_PARCode', how='inner') #, validate='one_to_one'
nomatch_wadar_isc_cas = (innerjoin.merge(paroms, left_on='AQUO_Codes', right_on='wadar_PARCode', how = 'left', indicator=True) #Alle ISC die niet met CASnummers kunnen worden gemapt
                        .query('_merge == "left_only"')
                        .drop('_merge', axis=1))

print('total can be mapped from wadar to ISC =', len(wadar_isc_cas), 
      '\n Cannot find match for ISC parameters with wadar', len(nomatch_wadar_isc_cas),
      '\n SUM', len(wadar_isc_cas)+ len(nomatch_wadar_isc_cas))

nomatch =nomatch_wadar_isc_cas.merge(leftjoin, on = 'Unieke identificatie gemeten parameter', how='outer', suffixes=("", "_r"))

# Identify overlapping non-key columns that exist on both sides
overlaps = set(nomatch_wadar_isc_cas.columns).intersection(leftjoin.columns) - set(['Unieke identificatie gemeten parameter'])

#%%
# Coalesce: prefer left, then right
for col in overlaps:
    nomatch[col] = nomatch[col].combine_first(nomatch.pop(f"{col}_r"))
wadar_isc_cas.to_csv(Path.joinpath(p.parent,'mappings/wadar-isc-cas.csv'), index=False)
nomatch.to_csv(Path.joinpath(p.parent,'mappings/nomatch-wadar-isc-cas.csv'), index=False)

with pd.ExcelWriter(Path.joinpath(p.parent,'mappings/parameter_e_h_g.xlsx')) as writer: 
    wadar_isc_cas.to_excel(writer, sheet_name='wadar_isc_cas', index=False)
    nomatch.to_excel(writer, sheet_name='nomatch_wadar_isc_cas', index=False) 

# %% location mapping mapping naar wadar uitgevoerd
# MET wadar een handmatige mapping is nodig aangezien de nieuwe terminologie te veel verschilt 
lsloc=wadar['locatie_code'].drop_duplicates().to_frame()
locs= locations[['Identitication unique de la station' , 'Localité']]
locs=locs.groupby(['Identitication unique de la station' , 'Localité']).count().reset_index()
locs=locs[locs['Identitication unique de la station'].str.startswith("NL")]

all_locs = locs.merge(lsloc, left_on='Localité', right_on='locatie_code', how='outer')
all_locs.to_csv(Path.joinpath(p.parent,'mappings/locations.csv'), index=False)
all_locs.to_excel(Path.joinpath(p.parent,'mappings/locations-raw.xlsx'), index=False)

# %%
# mapping van wadar HDH uniques met hoedanigheid codes uniques
