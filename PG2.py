# streamlit_app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import os

st.set_page_config(page_title="PG Run Analysis", layout="wide")
st.title("⚡ PG Run Analysis Dashboard v7.6")

# -------------------------------
# 1️⃣ File Upload
# -------------------------------
st.sidebar.header("Upload Files")
folder_upload = st.sidebar.file_uploader(
    "Upload multiple Excel/CSV files", 
    type=['xlsx','xls','csv'], 
    accept_multiple_files=True
)
reference_file = st.sidebar.file_uploader(
    "Upload Reference File", type=['xlsx','xls']
)

chunk_size = 100000  # for CSV

# -------------------------------
# 2️⃣ Session state
# -------------------------------
if 'all_data' not in st.session_state: st.session_state.all_data = pd.DataFrame()
if 'pg_kpi' not in st.session_state: st.session_state.pg_kpi = pd.DataFrame()
if 'outage_table' not in st.session_state: st.session_state.outage_table = pd.DataFrame()
if 'progress_val' not in st.session_state: st.session_state.progress_val = 0.0

# -------------------------------
# 3️⃣ Helper Functions
# -------------------------------
def fix_datetime(df, sheet_type):
    df = df.copy()
    df.columns = df.columns.str.strip()
    try:
        if sheet_type == 'Down Data':
            df['Start Time'] = pd.to_datetime(df['Occurred Date'].astype(str) + ' ' + df['Occurred Time'].astype(str), errors='coerce')
            df['End Time'] = pd.to_datetime(df['Restored Date'].astype(str) + ' ' + df['Restored Time'].astype(str), errors='coerce')
            df['Duration Hr'] = df['Duration (Min)']/60
            df['Alarm'] = df['Effect'].apply(lambda x: 'Outage' if x in ['Site Down','Site Down (Fluctuating)'] else None)
            df['Date'] = pd.to_datetime(df['Restored Date'], errors='coerce').dt.date
            df['Site ID'] = df['Site Code']
        elif sheet_type == 'Power Alarms':
            df['Start Time'] = pd.to_datetime(df['Alarm Raised Date'].astype(str)+' '+df['Alarm Raised Time'].astype(str), errors='coerce')
            df['End Time'] = pd.to_datetime(df['Cleared At Date'].astype(str)+' '+df['Cleared At Time'].astype(str), errors='coerce')
            df['Duration Hr'] = df['Duration (Hrs)']
            df['Alarm'] = df['Alarm Catagorey'].apply(lambda x: 'Power' if x=='M' else None)
            df['Date'] = pd.to_datetime(df['Alarm Raised Date'], errors='coerce').dt.date
            df['Site ID'] = df['Site']
        elif sheet_type == 'Reference':
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
            df['Start Time'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['Start Time'].astype(str), errors='coerce')
            df['End Time'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['End Time'].astype(str), errors='coerce')
            df['Duration Hr'] = df['Duration Hr']
            df['Alarm'] = 'PG run'
            df['Site ID'] = df['Site ID']
    except Exception as e:
        st.error(f"Error in fix_datetime for {sheet_type}: {e}")
    df = df[['Date','Site ID','Start Time','End Time','Duration Hr','Alarm']]
    return df

@st.cache_data
def get_site_date_list(all_data):
    site_list = sorted(all_data['Site ID'].unique())
    site_dates = {site: sorted(all_data[all_data['Site ID']==site]['Date'].astype(str).unique())
                  for site in site_list}
    return site_list, site_dates

def calculate_kpi(group):
    res = {}
    pg = group[group['Alarm']=='PG run']
    power = group[group['Alarm']=='Power']
    outage = group[group['Alarm']=='Outage']
    
    try:
        # PG run KPI
        if not pg.empty:
            first_pg_start = pg['Start Time'].min()
            max_pg_end = pg['End Time'].max()
            res['1st PG run Time'] = round(first_pg_start.hour + first_pg_start.minute/60,2)
            res['Max/last PG run Start Time'] = round(pg['Start Time'].max().hour + pg['Start Time'].max().minute/60,2)
            res['Max/Stop PG run Time'] = round(max_pg_end.hour + max_pg_end.minute/60,2)
            res['Total PG run'] = round(pg['Duration Hr'].sum(),2)
            res['Max PG run'] = round(pg['Duration Hr'].max(),2)
            res['Frequency PG run'] = pg.shape[0]
        else:
            first_pg_start = None
            max_pg_end = None
            res.update({'1st PG run Time':None,'Max/last PG run Start Time':None,'Max/Stop PG run Time':None,
                        'Total PG run':0,'Max PG run':0,'Frequency PG run':0})
        
        # Power KPI
        res['Total Power alarm'] = round(power['Duration Hr'].sum(),2) if not power.empty else 0
        res['Max Power alarm'] = round(power['Duration Hr'].max(),2) if not power.empty else 0
        
        # Before 1st PG run Power alarm
        if first_pg_start is not None and not power.empty:
            candidate_power = power[power['Start Time'] < first_pg_start]
            if not candidate_power.empty:
                last_before_pg = candidate_power.loc[candidate_power['Start Time'].idxmax()]
                res['Before 1st PG run Power alarm'] = round(last_before_pg['Start Time'].hour + last_before_pg['Start Time'].minute/60,2)
            else:
                res['Before 1st PG run Power alarm'] = None
        else:
            res['Before 1st PG run Power alarm'] = None
        
        # 1st Outage after PG run
        if first_pg_start is not None and not outage.empty:
            after_pg_outages = outage[outage['End Time'] > first_pg_start]
            if not after_pg_outages.empty:
                res['After PG run Outage End Time'] = round(after_pg_outages['End Time'].min().hour + after_pg_outages['End Time'].min().minute/60,2)
            else:
                res['After PG run Outage End Time'] = None
        else:
            res['After PG run Outage End Time'] = None
        
        # Outage during PG run
        if first_pg_start is not None and max_pg_end is not None and not outage.empty:
            outage_in_pg = outage[(outage['Start Time'] >= first_pg_start) & (outage['End Time'] <= max_pg_end)]
            res['Outage during PG run'] = 'Yes' if not outage_in_pg.empty else 'No'
        else:
            res['Outage during PG run'] = 'No'
        
        # Site Up after PG run
        after_outage_end = res.get('After PG run Outage End Time')
        if first_pg_start is not None and after_outage_end is not None:
            diff_hr = after_outage_end - (first_pg_start.hour + first_pg_start.minute/60)
            res['Site Up after PG run'] = "Site Up by PG run" if diff_hr <= 0.25 else "False PG run & site not up"
        else:
            res['Site Up after PG run'] = None
    except Exception as e:
        st.error(f"Error in calculate_kpi: {e}")
    
    return pd.Series(res)

# -------------------------------
# 4️⃣ Analysis Trigger
# -------------------------------
if folder_upload and reference_file:
    if st.sidebar.button("Analysis PG run"):
        try:
            st.session_state.progress_val = 0.0
            progress = st.progress(st.session_state.progress_val)
            
            # Step 1: Reference
            st.info("Step 1: Loading Reference File...")
            df_ref = pd.read_excel(reference_file)
            df_ref = fix_datetime(df_ref,'Reference')
            st.session_state.progress_val = 0.125
            progress.progress(st.session_state.progress_val)
            st.success("✅ Reference Loaded")
            
            # Step 2: Filter uploaded files
            st.info("Step 2: Processing uploaded files...")
            ref_sites_dates = df_ref[['Site ID','Date']].drop_duplicates()
            filtered_data = []
            total_files = len(folder_upload)
            
            for i, uploaded_file in enumerate(folder_upload):
                name, ext = os.path.splitext(uploaded_file.name)
                if ext.lower() in ['.xlsx','.xls']:
                    xls = pd.ExcelFile(uploaded_file)
                    for sheet in xls.sheet_names:
                        if sheet in ['Down Data','Power Alarms']:
                            df = pd.read_excel(uploaded_file, sheet_name=sheet)
                            df_sheet = fix_datetime(df, sheet)
                            df_sheet = df_sheet.merge(ref_sites_dates, on=['Site ID','Date'], how='inner')
                            filtered_data.append(df_sheet)
                elif ext.lower() == '.csv':
                    for chunk in pd.read_csv(uploaded_file, chunksize=chunk_size):
                        chunk = chunk.merge(ref_sites_dates, on=['Site ID','Date'], how='inner')
                        filtered_data.append(chunk)
                st.session_state.progress_val = 0.125 + (0.5*i/total_files)
                progress.progress(st.session_state.progress_val)
            
            all_data = pd.concat([df_ref]+filtered_data, ignore_index=True)
            st.session_state.all_data = all_data
            st.session_state.progress_val = 0.65
            progress.progress(st.session_state.progress_val)
            st.success("✅ All Data Compiled")
            
            # Step 3: KPI
            st.info("Step 3: Calculating KPI...")
            pg_kpi = all_data.groupby(['Site ID','Date']).apply(calculate_kpi).reset_index()
            st.session_state.pg_kpi = pg_kpi
            st.session_state.progress_val = 0.85
            progress.progress(st.session_state.progress_val)
            st.success("✅ KPI Calculated")
            
            # Step 4: Outage Table
            st.info("Step 4: Preparing Outage Table...")
            st.session_state.outage_table = all_data[all_data['Alarm']=='Outage']
            st.session_state.progress_val = 0.95
            progress.progress(st.session_state.progress_val)
            st.success("✅ Outage Table Ready")
            
            # Step 5: Dashboard Ready
            st.session_state.progress_val = 1.0
            progress.progress(st.session_state.progress_val)
            st.success("🎉 Dashboard Ready!")
            
        except Exception as e:
            st.error(f"Error during analysis: {e}")

# -------------------------------
# 5️⃣ Dashboard Display
# -------------------------------
if not st.session_state.all_data.empty:
    st.subheader("Select Site ID and Date")
    site_list, site_dates_dict = get_site_date_list(st.session_state.all_data)
    selected_site = st.selectbox("Site ID", site_list)
    selected_date = st.selectbox("Date", site_dates_dict[selected_site])
    
    filtered_site_data = st.session_state.all_data[
        (st.session_state.all_data['Site ID']==selected_site) &
        (st.session_state.all_data['Date'].astype(str)==selected_date)
    ]
    
    filtered_kpi = st.session_state.pg_kpi[
        (st.session_state.pg_kpi['Site ID']==selected_site) &
        (st.session_state.pg_kpi['Date'].astype(str)==selected_date)
    ]
    
    # KPI Display
    st.subheader("KPI Summary")
    kpi_names = [
        'Total Power alarm','Total PG run','Max Power alarm','Max PG run','Frequency PG run',
        '1st PG run Time','Max/last PG run Start Time','Before 1st PG run Power alarm',
        'After PG run Outage End Time','Outage during PG run','Site Up after PG run','Max/Stop PG run Time'
    ]
    cols = st.columns(4)
    for i, kpi in enumerate(kpi_names):
        value = filtered_kpi[kpi].values[0] if kpi in filtered_kpi.columns else None
        cols[i % 4].metric(label=kpi, value=value)
    
    # Outage table
    st.subheader("Outage Table")
    st.dataframe(filtered_site_data[['Site ID','Date','Start Time','End Time','Duration Hr','Alarm']])
    
    # Timeline chart
    st.subheader("Timeline Chart")
    fig = px.timeline(
        filtered_site_data,
        x_start="Start Time",
        x_end="End Time",
        y="Alarm",
        color="Alarm",
        color_discrete_map={"PG run":"green","Outage":"red","Power":"yellow"}
    )
    fig.update_xaxes(tickformat="%H:%M", title="Time (HH:MM)")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    # Download buttons
    st.subheader("Download Options")
    st.download_button(
        "Download Filtered Data CSV",
        filtered_site_data.to_csv(index=False).encode('utf-8'),
        f"{selected_site}_{selected_date}_Data.csv",
        "text/csv"
    )
    st.download_button(
        "Download Filtered KPI CSV",
        filtered_kpi.to_csv(index=False).encode('utf-8'),
        f"{selected_site}_{selected_date}_KPI.csv",
        "text/csv"
    )
    st.download_button(
        "Download Full KPI Data CSV",
        st.session_state.pg_kpi.to_csv(index=False).encode('utf-8'),
        "All_Site_KPI_Data.csv",
        "text/csv"
    )
