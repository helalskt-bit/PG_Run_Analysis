# app.py
# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime
import io
import time
import gc
import os

# -------------------------------------------------------
#  Page Setup
# -------------------------------------------------------
st.set_page_config(
    page_title="Diesel Generator Run Hour Analysis",
    page_icon="⛽️",
    layout="wide"
)

# ---------- Banner ----------
st.markdown("""
<div style="
    background: linear-gradient(90deg, #8A2BE2, #DA70D6);
    padding: 20px;
    border-radius: 15px;
    text-align: center;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    margin-bottom: 25px;
">
<img src="https://cdn-icons-png.flaticon.com/512/2965/2965304.png" width="55"
     style="vertical-align:middle; margin-right:12px; animation: pulse 2s infinite;">
<span style="color:white; font-size:30px; font-weight:800; vertical-align:middle;">
    Diesel Generator RH Analysis Tools
</span>
<p style="color:#f8f8f8; font-size:16px; font-weight:500; margin-top:8px;">
    📊 Comprehensive Run Hour Verification & KPI Dashboard
</p>
</div>
<style>
@keyframes pulse {
  0% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.1); opacity: 0.8; }
  100% { transform: scale(1); opacity: 1; }
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------
# KPI Styles
# -------------------------------------------------------
st.markdown("""
<style>
.kpi-card {
  background: linear-gradient(145deg, #caa3ee, #9b59b6);
  color: #000;
  padding: 18px;
  border-radius: 16px;
  box-shadow: 8px 8px 20px rgba(0,0,0,0.18);
  text-align: center;
  font-weight: 800;
  transition: transform 0.35s ease;
}
.kpi-card:hover { transform: translateY(-6px) scale(1.02); }
.kpi-title { font-size:14px; margin-bottom:8px; color:#000; }
.kpi-value { font-size:28px; color:#000; font-weight:900; }
.kpi-sub { font-size:12px; color:#000; margin-top:6px; opacity:0.9; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------
# Helper functions (optimized for memory)
# -------------------------------------------------------
def normalize_cols(cols):
    return [re.sub(r"\s+", "_", str(c).strip().lower()) for c in cols]

def normalize_site(v):
    if pd.isna(v): return np.nan
    s = str(v).replace("\u00a0","").replace("\u200b","").replace("-","_")
    s = re.sub(r"[^A-Za-z0-9_]", "", s).strip().upper()
    return s if s else np.nan

def reduce_memory(df):
    """Downcast numeric and convert object to category when possible."""
    for col in df.select_dtypes(include=["float", "int"]).columns:
        df[col] = pd.to_numeric(df[col], downcast="float")
    for col in df.select_dtypes(include="object").columns:
        if df[col].nunique() < df.shape[0] / 2:
            df[col] = df[col].astype("category")
    return df

@st.cache_data(ttl=600, max_entries=5)
def read_file_bytes(file_bytes, filename, usecols=None):
    """Read uploaded file bytes into DataFrame (cached, optimized)."""
    if filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes), usecols=usecols)
    else:
        df = pd.read_excel(io.BytesIO(file_bytes), usecols=usecols, engine="openpyxl")
    return reduce_memory(df)

def read_any(uploaded_file, usecols=None):
    b = uploaded_file.read()
    df = read_file_bytes(b, uploaded_file.name, usecols)
    df.columns = normalize_cols(df.columns)
    return df

# KPI card helper
def render_kpi_card(title, value_display, value_numeric, subtitle, df_for_download, key):
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f'<div class="kpi-card" id="{key}">', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-title">{title}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{value_display}</div>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(f'<div class="kpi-sub">{subtitle}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        if isinstance(value_numeric, (int, float)):
            try:
                st.progress(int(round(min(max(value_numeric, 0), 100))))
            except:
                pass
        if df_for_download is not None:
            csv_bytes = df_for_download.to_csv(index=False).encode()
            st.download_button(f"⬇️ Download {title}", csv_bytes,
                               file_name=f"{title.replace(' ','_')}.csv", mime="text/csv")
    st.write("")

# -------------------------------------------------------
# Sidebar Upload + Run
# -------------------------------------------------------
with st.sidebar.expander("🔁 Upload / Run"):
    st.sidebar.markdown("### 📂 Upload files")
    main_files = st.sidebar.file_uploader("Main File(s)", ["csv","xlsx"], accept_multiple_files=True)
    ref_file = st.sidebar.file_uploader("Reference File", ["csv","xlsx"])
    run_button = st.sidebar.button("▶️ Process Data")

progress_bar = st.sidebar.progress(0)
progress_text = st.sidebar.empty()

if not run_button:
    st.sidebar.info("Upload files and click **Process Data** to run the analysis.")
    st.stop()

# -------------------------------------------------------
# Step 1 — Read files
# -------------------------------------------------------
progress_text.info("Step 1/5 — Reading files...")
progress_bar.progress(5)

if not main_files or not ref_file:
    st.error("Please upload both Main and Reference files.")
    st.stop()

use_cols_main = ["Site", "Alarm_Slogan", "Alarm_Raised_Date", "Duration_hrs"]
use_cols_ref = ["Site_ID", "Previous_Refuelling_Date", "Present_Refuelling_Date", "Claimed_RH"]

try:
    df_ref = read_any(ref_file, usecols=use_cols_ref)
    df_all_list = []
    for f in main_files:
        df_tmp = read_any(f, usecols=use_cols_main)
        df_tmp["__source_file__"] = f.name
        df_all_list.append(df_tmp)
except Exception as e:
    st.error(f"Error reading files: {e}")
    st.stop()

if not df_all_list:
    st.error("No valid data loaded.")
    st.stop()

progress_bar.progress(20)
progress_text.info("Step 2/5 — Cleaning and normalizing data.")

# -------------------------------------------------------
# Step 2 — Normalize + Prepare
# -------------------------------------------------------
df_ref.columns = normalize_cols(df_ref.columns)
if "site_id" not in df_ref.columns and "site" in df_ref.columns:
    df_ref.rename(columns={"site":"site_id"}, inplace=True)
df_ref["__site_key__"] = df_ref["site_id"].map(normalize_site)

for c in ["previous_refuelling_date", "present_refuelling_date"]:
    df_ref[c] = pd.to_datetime(df_ref.get(c), errors="coerce", dayfirst=True)

df_ref["day_difference"] = (df_ref["present_refuelling_date"] - df_ref["previous_refuelling_date"]).dt.days.fillna(0).astype(int)
df_ref["total_available_hr"] = df_ref["day_difference"] * 24
df_ref["claimed_rh"] = pd.to_numeric(df_ref.get("claimed_rh", 0), errors="coerce").fillna(0)
df_ref["average_dgrh"] = np.where(df_ref["day_difference"] > 0,
                                  df_ref["claimed_rh"] / df_ref["day_difference"], 0)

df_ref.drop_duplicates("__site_key__", inplace=True)

df_all = pd.concat(df_all_list, ignore_index=True)
df_all.columns = normalize_cols(df_all.columns)
del df_all_list; gc.collect()

progress_bar.progress(40)
progress_text.info("Step 3/5 — Merging and filtering.")

# -------------------------------------------------------
# Step 3 — Merge & Filter
# -------------------------------------------------------
df_all["duration_hrs"] = pd.to_numeric(df_all["duration_hrs"], errors="coerce").fillna(0)
df_all["__site_key__"] = df_all["site"].map(normalize_site)
df_all["alarm_raised_date"] = pd.to_datetime(df_all["alarm_raised_date"], errors="coerce", dayfirst=True)

merged = df_all.merge(
    df_ref[["__site_key__", "previous_refuelling_date", "present_refuelling_date"]],
    on="__site_key__", how="inner"
)
mask = (
    (merged["alarm_raised_date"] >= merged["previous_refuelling_date"]) &
    (merged["alarm_raised_date"] <= merged["present_refuelling_date"])
)
merged = merged.loc[mask].copy()

progress_bar.progress(60)
progress_text.info("Step 4/5 — Aggregating and computing KPIs.")

# -------------------------------------------------------
# Step 4 — Aggregation & KPI calculations
# -------------------------------------------------------
merged["mg"] = ""
merged.loc[merged["alarm_slogan"].str.contains(r"(mains|grid)", case=False, na=False), "mg"] = "M"
merged.loc[merged["alarm_slogan"].str.contains(r"(genset|generator|dg\\b)", case=False, na=False), "mg"] = "G"

agg = merged.groupby(["__site_key__", "mg"])["duration_hrs"].sum().unstack(fill_value=0)
agg.rename(columns={"G":"genset_rh","M":"mains_failed_hr"}, inplace=True)

df_out = df_ref.merge(agg, on="__site_key__", how="left").fillna(0)
df_out["actual_mains_failed_hr"] = df_out["mains_failed_hr"] + df_out["genset_rh"]
df_out["grid_availability_pct"] = (1 - (df_out["actual_mains_failed_hr"] / df_out["total_available_hr"])) * 100
df_out["grid_availability_pct"] = df_out["grid_availability_pct"].clip(0,100)

df_out["rh_difference"] = df_out["claimed_rh"] - df_out["genset_rh"]
df_out["pct_of_rh_difference"] = np.where(df_out["claimed_rh"] != 0,
                                          (df_out["rh_difference"] / df_out["claimed_rh"]) * 100, np.nan)
df_out["matching_rh"] = np.where((abs(df_out["pct_of_rh_difference"]) <= 5) |
                                 (abs(df_out["rh_difference"]) <= 5), "Yes", "No")

progress_bar.progress(90)
progress_text.info("Step 5/5 — Finalizing and displaying results.")

# -------------------------------------------------------
# Step 5 — KPIs
# -------------------------------------------------------
total_sites = df_out["__site_key__"].nunique()
claimed_match_count = df_out.loc[df_out["matching_rh"]=="Yes","__site_key__"].nunique()
alarm_not_trigger_count = df_out.loc[(df_out["matching_rh"]=="No") & 
                                     (df_out["claimed_rh"]>df_out["genset_rh"]),
                                     "__site_key__"].nunique()
false_alarm_trigger_count = df_out.loc[(df_out["matching_rh"]=="No") & 
                                       (df_out["claimed_rh"]<=df_out["genset_rh"]),
                                       "__site_key__"].nunique()

claimed_matching_rate_pct = round((claimed_match_count/total_sites)*100,2)
alarm_not_trigger_pct = round((alarm_not_trigger_count/total_sites)*100,2)
false_alarm_trigger_pct = round((false_alarm_trigger_count/total_sites)*100,2)

progress_bar.progress(100)
progress_text.success("All steps completed ✅")

# -------------------------------------------------------
# Tabs: Raw / Summary / KPI
# -------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📄 Raw Data", "📘 Summary", "📊 KPI"])

with tab1:
    st.subheader("Raw filtered data")
    st.dataframe(merged.reset_index(drop=True), use_container_width=True)
    st.download_button("⬇️ Download Raw CSV",
                       merged.to_csv(index=False).encode(),
                       file_name=f"DG_Raw_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                       mime="text/csv")

with tab2:
    st.subheader("Summary Table")
    df_out_disp = df_out.copy()
    df_out_disp["grid_availability_pct"] = df_out_disp["grid_availability_pct"].round(2).astype(str)+"%"
    st.dataframe(df_out_disp.reset_index(drop=True), use_container_width=True)
    st.download_button("⬇️ Download Summary CSV",
                       df_out.to_csv(index=False).encode(),
                       file_name=f"DG_Summary_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                       mime="text/csv")

with tab3:
    st.subheader("KPI Dashboard")
    render_kpi_card("Claimed Matching Rate (%)", f"{claimed_matching_rate_pct}%", claimed_matching_rate_pct,
                    f"{claimed_match_count}/{total_sites} sites matched", df_out[df_out["matching_rh"]=="Yes"], "kpi1")
    render_kpi_card("Alarm Not Trigger (%)", f"{alarm_not_trigger_pct}%", alarm_not_trigger_pct,
                    f"{alarm_not_trigger_count}/{total_sites} sites", 
                    df_out[(df_out["matching_rh"]=="No") & (df_out["claimed_rh"]>df_out["genset_rh"])], "kpi2")
    render_kpi_card("False Alarm Trigger (%)", f"{false_alarm_trigger_pct}%", false_alarm_trigger_pct,
                    f"{false_alarm_trigger_count}/{total_sites} sites", 
                    df_out[(df_out["matching_rh"]=="No") & (df_out["claimed_rh"]<=df_out["genset_rh"])], "kpi3")

# -------------------------------------------------------
# Footer
# -------------------------------------------------------
st.markdown("---")
st.markdown("""
**Notes & Recommendations**
- Use smaller CSV/XLSX files or limit columns.
- Avoid uploading >200 MB total; use zipped or split files if needed.
- This app automatically compresses data types to save memory.
""")
