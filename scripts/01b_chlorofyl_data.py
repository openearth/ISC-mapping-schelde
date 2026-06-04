#%% work with data in different format
# script to prep the chlorophyl-a data. Is prepped and works. 
import pandas as pd
import os
from pathlib import Path
p=Path(os.getcwd())

schaarvd = pd.read_excel(Path.joinpath(p.parent, 
                                       'voorbeeld/isc_2023-2025/SCHAARVODDL + SASVGT_CHLfa_2023-2025.xlsx'), 
                                       sheet_name='SCHAARVODDL CHLfa')
sasvgt = pd.read_excel(Path.joinpath(p.parent, 
                                       'voorbeeld/isc_2023-2025/SCHAARVODDL + SASVGT_CHLfa_2023-2025.xlsx'), 
                                       sheet_name='SASVGT CHLfa')


locatie = pd.DataFrame({
    'iscformat': ['NL89_SASVGT','NL89_SCHAARVODDL'], 
    'rwsformat': ['SASVGT','SCHAARVODDL']
})

columns = ["uid", "PARAMETRE", "n° CAS nr", 
        "Unieke identificatie gemeten parameter", "Unieke eenheidsidentificatie", 'ComponentName']
values = [1439, 'Chlorophylle a', '479-61-8', 'Chlorofyl a', 'µg/L','CHLFa'] ## quick fix to chlorofyl-a. if other parameters are used, this needs to be adjusted in the function

parameter_df = pd.DataFrame([values], columns=columns)
#hoedanigheid is only NVT -> EB in this dataset
# make a function to apply to both datasets, first fix the data before applying the function
def run_function_on_data(df, locatie, parameter):
    cols = [ 'ComponentName', 'UHoedanigheid', 'ResultType', 'UMeetpunt',
        'ResultText', 'ResultUMeetonzekerheid', 'ResultValue','UGeplandeDatum'] 
    df = df[cols]
    meetpunt = df['UMeetpunt'].unique()
    locatie_code = locatie[locatie['rwsformat']==meetpunt[0]]
    df['Unieke identiticatie meetpunt'] = df['UMeetpunt'].replace(meetpunt, locatie_code['iscformat'].values[0])
    df['Geanalyseerde fractie'] = df['UHoedanigheid'].replace('NVT', 'EB')
    df['Datum staalname'] =  pd.to_datetime(df['UGeplandeDatum'], format="mixed").dt.strftime('%d/%m/%Y') 
    df['kwantificeringsgrens_bool'] = df['ResultText'].str.contains('<', regex=True)
    df['Aanpak kwantificeringsgrens'] = df['kwantificeringsgrens_bool'].apply(lambda x: '<' if x else '=')
    df['Resultaat'] = df['ResultValue'].replace(-999.0, 'NV')
    df['Unieke identificatie gemeten parameter'] = parameter["uid"].values[0]
    final_cols = ['Unieke identiticatie meetpunt', 'Geanalyseerde fractie',
       'Datum staalname', 
       'Aanpak kwantificeringsgrens', 'Resultaat',
       'Unieke identificatie gemeten parameter']
    
    df = df[final_cols]
    return df
# in resulttype zit de kwantificeringsgrens + aquo_code, onderverdelen in kwantificeringsgrens + wat de waare is
# %%r
schaar_output= run_function_on_data(schaarvd, locatie, parameter_df)
# %%
sasvgt_output = run_function_on_data(sasvgt, locatie, parameter_df)
# %%
