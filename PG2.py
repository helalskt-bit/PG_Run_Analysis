# app.py
# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime
import io
import time

# -------------------------------------------------------
#  Page Setup
# -------------------------------------------------------
st.set_page_config(
    page_title="Diesel Generator Run Hour Analysis",
    page_icon="⛽️",
    layout="wide"
)

# ---------- Subject Banner (with image & gradient) ----------
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
#  Styles (KPI cards)
# -------------------------------------------------------
KPI_CARD_CSS = """
<style>
.kpi-card {
  background: linear-gradient(145deg, #caa3ee, #9b59b6);
  color: #000;
  padding: 18px;
  border-radius: 16px;
  box-shadow: 8px 8px 20px rgba(0,0,0,0.18), -6px -6px 18px rgba(255,255,255,0.06);
  text-align: center;
  font-weight: 800;
  transition: transform 0.35s ease, box-shadow 0.35s ease;
}
.kpi-card:hover {
  transform: translateY(-6px) rotate(-0.5deg) scale(1.02);
  box-shadow: 12px 12px 30px rgba(0,0,0,0.24), -8px -8px 24px rgba(255,255,255,0.06);
}
.kpi-title { font-size:14px; margin-bottom:8px; color:#000; }
.kpi-value { font-size:28px; color:#000; font-weight:900; }
.kpi-sub { font-size:12px; color:#000; margin-top:6px; opacity:0.9; }
</style>
"""
st.markdown(KPI_CARD_CSS, unsafe_allow_html=True)

# ---------- Styles (KPI card + small animation) ----------
KPI_CARD_CSS = """
<style>
.kpi-card {
  background: linear-gradient(145deg, #caa3ee, #9b59b6);
  color: #000;
  padding: 18px;
  border-radius: 16px;
  box-shadow: 8px 8px 20px rgba(0,0,0,0.18), -6px -6px 18px rgba(255,255,255,0.06);
  text-align: center;
  font-weight: 800;
  transition: transform 0.35s ease, box-shadow 0.35s ease;
}
.kpi-card:hover {
  transform: translateY(-6px) rotate(-0.5deg) scale(1.02);
  box-shadow: 12px 12px 30px rgba(0,0,0,0.24), -8px -8px 24px rgba(255,255,255,0.06);
}
.kpi-title { font-size:14px; margin-bottom:8px; color:#000; }
.kpi-value { font-size:28px; color:#000; font-weight:900; }
.kpi-sub { font-size:12px; color:#000; margin-top:6px; opacity:0.9; }
.small-muted { font-size:12px; color:#666; }
.icon-badge { font-size:22px; padding-right:8px; }
</style>
"""

st.markdown(KPI_CARD_CSS, unsafe_allow_html=True)

# ---------- Helper functions ----------
def normalize_cols(cols):
    return [re.sub(r"\s+", "_", str(c).strip().lower()) for c in cols]

def normalize_site(v):
    if pd.isna(v): return np.nan
    s = str(v).replace("\u00a0","").replace("\u200b","").replace("-","_")
    s = re.sub(r"[^A-Za-z0-9_]", "", s).strip().upper()
    return s if s else np.nan

@st.cache_data
def read_file_bytes(file_bytes, filename):
    """Read uploaded file bytes into DataFrame (cached)"""
    if filename.endswith(".csv"):
        return pd.read_csv(io.BytesIO(file_bytes))
    else:
        return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")

def read_any(uploaded_file):
    b = uploaded_file.read()
    df = read_file_bytes(b, uploaded_file.name)
    df.columns = normalize_cols(df.columns)
    return df

def safe_div(a, b):
    return np.where((b == 0) | pd.isna(b), 0, a / b)

def make_download_bytes(df, filename):
    return (df.to_csv(index=False).encode(), filename, "text/csv")

# KPI card renderer (returns three columns layout)
def render_kpi_card(title, value_display, value_numeric, subtitle, df_for_download, key):
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f'<div class="kpi-card" id="{key}">', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-title">📌 <span class="kpi-title">{title}</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{value_display}</div>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(f'<div class="kpi-sub">{subtitle}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Mini progress visual for percent KPIs
        if isinstance(value_numeric, (int, float)):
            try:
                pct = int(round(min(max(value_numeric, 0), 100)))
                st.progress(pct)
            except Exception:
                pass

        # Download button below the card
        if df_for_download is not None:
            csv_bytes = df_for_download.to_csv(index=False).encode()
            st.download_button(f"⬇️ Download {title}", csv_bytes, file_name=f"{title.replace(' ','_')}.csv", mime="text/csv")
    # Add some spacing
    st.write("")

# ---------- Sidebar Upload + Progress ----------
with st.sidebar.expander("🔁 Upload / Run"):
    st.sidebar.markdown("### 📂 Upload files")
    main_files = st.sidebar.file_uploader("Main File(s) (csv/xlsx)", ["csv","xlsx"], accept_multiple_files=True)
    ref_file = st.sidebar.file_uploader("Reference File (csv/xlsx)", ["csv","xlsx"])
    run_button = st.sidebar.button("▶️ Process Data")

# Sidebar progress area
progress_bar = st.sidebar.progress(0)
progress_text = st.sidebar.empty()

# If user didn't press Run, still allow upload and show message
if not run_button:
    st.sidebar.info("Upload files and click **Process Data** to run the analysis.")
    # Keep UI interactive but stop main flow until user presses Run
    st.stop()

# ---------- Step 1: Read files ----------
progress_text.info("Step 1/5 — Reading files...")
progress_bar.progress(5)
time.sleep(0.15)

if not main_files or not ref_file:
    st.error("Please upload both Main file(s) and Reference file in the sidebar.")
    st.stop()

# Read reference
try:
    df_ref = read_any(ref_file)
except Exception as e:
    st.error(f"Error reading reference file: {e}")
    st.stop()

# Read all mains
df_all_list = []
for f in main_files:
    try:
        df_tmp = read_any(f)
        df_tmp["__source_file__"] = f.name
        df_all_list.append(df_tmp)
    except Exception as e:
        st.error(f"Error reading {f.name}: {e}")
        st.stop()

if not df_all_list:
    st.error("No main file data read.")
    st.stop()

progress_bar.progress(20)
progress_text.info("Files loaded. Step 2/5 — Normalizing and validating columns.")
time.sleep(0.15)

# ---------- Normalize columns ----------
df_ref.columns = normalize_cols(df_ref.columns)
df_ref.rename(columns={
    "bl__office": "bl_office",
    "generic__code": "generic_code",
    "site__id": "site_id",
    "previous__refuelling__date": "previous_refuelling_date",
    "present__refuelling__date": "present_refuelling_date",
    "claimed_rh": "claimed_rh"
}, inplace=True, errors="ignore")

# Ensure Site_ID column exists as original name for display (keep original if present)
if "site_id" not in df_ref.columns and "site" in df_ref.columns:
    df_ref = df_ref.rename(columns={"site":"site_id"})

# create site key and parse dates
df_ref["__site_key__"] = df_ref["site_id"].map(normalize_site)
for c in ["previous_refuelling_date", "present_refuelling_date"]:
    if c in df_ref.columns:
        df_ref[c] = pd.to_datetime(df_ref[c], errors="coerce", dayfirst=True)
    else:
        df_ref[c] = pd.NaT

# Day difference and total hours
df_ref["day_difference"] = (df_ref["present_refuelling_date"] - df_ref["previous_refuelling_date"]).dt.days.fillna(0).astype(int)
df_ref["total_available_hr"] = df_ref["day_difference"] * 24

# Average DGRH = Claimed_RH / Day_difference (guard divis by zero)
df_ref["claimed_rh"] = pd.to_numeric(df_ref.get("claimed_rh", 0), errors="coerce").fillna(0)
df_ref["average_dgrh"] = np.where(df_ref["day_difference"] > 0, df_ref["claimed_rh"] / df_ref["day_difference"], 0)

# Drop duplicate site keys keeping first
if df_ref["__site_key__"].duplicated().any():
    df_ref = df_ref.drop_duplicates("__site_key__", keep="first")

# Concatenate mains
df_all = pd.concat(df_all_list, ignore_index=True)
df_all.columns = normalize_cols(df_all.columns)

# ---------- Robust duration detection ----------
possible_keywords = ["duration","dur","hrs","hours","runtime","run_time","rh"]
keyword_matches = [c for c in df_all.columns if any(k in c.lower() for k in possible_keywords)]
numeric_cols = [c for c in df_all.columns if pd.api.types.is_numeric_dtype(df_all[c])]
numeric_valid = [c for c in numeric_cols if df_all[c].notna().sum() > 0 and df_all[c].abs().sum() > 0]

candidates = []
for c in (keyword_matches + numeric_valid):
    if c not in candidates:
        candidates.append(c)

if len(candidates) == 1:
    dur_col = candidates[0]
elif len(candidates) > 1:
    # prefer exact match 'duration_hrs' or 'duration'
    preferred = next((c for c in candidates if re.search(r"duration|duration_hrs|durationhr|dur_hrs", c, re.I)), None)
    dur_col = preferred if preferred else candidates[0]
else:
    st.error("No Duration column detected automatically. Please include a column name containing 'duration' or 'hrs'.")
    st.stop()

# ensure required columns exist
required_cols = ["site", "alarm_slogan", "alarm_raised_date"]
missing_cols = [c for c in required_cols if c not in df_all.columns]
if missing_cols:
    st.error(f"Missing required columns in main file(s): {', '.join(missing_cols)}")
    st.stop()

# convert values
df_all["duration_hrs"] = pd.to_numeric(df_all[dur_col], errors="coerce").fillna(0)
df_all["__site_key__"] = df_all["site"].map(normalize_site)
df_all["alarm_raised_date"] = pd.to_datetime(df_all["alarm_raised_date"], errors="coerce", dayfirst=True)

progress_bar.progress(40)
progress_text.info("Step 3/5 — Merging and filtering by refuelling window.")
time.sleep(0.15)

# ---------- Merge & filter within refuelling window ----------
merged = df_all.merge(
    df_ref[["__site_key__", "previous_refuelling_date", "present_refuelling_date"]],
    on="__site_key__", how="inner"
)
mask = (
    (merged["alarm_raised_date"] >= merged["previous_refuelling_date"]) &
    (merged["alarm_raised_date"] <= merged["present_refuelling_date"])
)
merged = merged.loc[mask].copy()

# ---------- Tag M/G ----------
mg_mains = r"(mains|ac\s*mains|grid\s*fail|grid\s*down)"
mg_gen   = r"(genset|generator|dg\b|diesel\s*gen)"
merged["mg"] = pd.Series(dtype="string")
merged.loc[merged["alarm_slogan"].str.contains(mg_mains, case=False, na=False), "mg"] = "M"
merged.loc[merged["alarm_slogan"].str.contains(mg_gen, case=False, na=False), "mg"] = "G"

progress_bar.progress(60)
progress_text.info("Step 4/5 — Aggregating and calculating summary metrics.")
time.sleep(0.15)

# ---------- Aggregation ----------
agg = merged.groupby(["__site_key__", "mg"])["duration_hrs"].sum().unstack(fill_value=0)
agg.rename(columns={"G": "genset_rh", "M": "mains_failed_hr"}, inplace=True)

# ---------- Summary Calculations ----------
# Merge agg into ref (left) so all ref sites present
df_out = df_ref.merge(agg, on="__site_key__", how="left").fillna(0)

df_out["actual_mains_failed_hr"] = df_out.get("mains_failed_hr", 0) + df_out.get("genset_rh", 0)

# Grid availability %
df_out["grid_availability_pct"] = (1 - (df_out["actual_mains_failed_hr"] / df_out["total_available_hr"])) * 100
df_out["grid_availability_pct"] = df_out["grid_availability_pct"].clip(0,100).fillna(0)

# RH difference and percent
df_out["rh_difference"] = df_out["claimed_rh"] - df_out.get("genset_rh", 0)
df_out["pct_of_rh_difference"] = np.where(df_out["claimed_rh"] != 0, (df_out["rh_difference"] / df_out["claimed_rh"]) * 100, np.nan)

# Matching logic
df_out["matching_rh"] = np.where(
    (abs(df_out["pct_of_rh_difference"]) <= 5) | (abs(df_out["rh_difference"]) <= 5),
    "Yes", "No"
)

# Ensure Average DGRH from df_ref carried over
if "average_dgrh" not in df_out.columns:
    df_out["average_dgrh"] = df_out.apply(lambda r: r["claimed_rh"] / r["day_difference"] if r["day_difference"]>0 else 0, axis=1)

# ---------- DG_RH>=10 raw extraction ----------
raw = merged[["site", "alarm_raised_date", "duration_hrs", "alarm_slogan", "mg", "__source_file__"]].copy()
raw.rename(columns={
    "site": "site_id",
    "alarm_raised_date": "date",
    "duration_hrs": "duration_hr",
    "alarm_slogan": "alarm_slogan",
    "mg": "alarm_type",
    "__source_file__": "source_file"
}, inplace=True)

raw["dg_rh_ge_10"] = np.where((raw["alarm_type"]=="G") & (raw["duration_hr"]>=10), raw["duration_hr"].round(2), "No")

dg10_dates = (
    raw.loc[(raw["alarm_type"]=="G") & (raw["duration_hr"]>=10)]
    .groupby("site_id")["date"]
    .apply(lambda x: sorted(x.dt.strftime("%Y-%m-%d").unique()))
    .reset_index()
)

if not dg10_dates.empty:
    dg10_expanded = pd.DataFrame.from_records(dg10_dates["date"].apply(lambda x: dict(enumerate(x))))
    dg10_expanded = dg10_expanded.add_prefix("dg_date_")
    dg10_combined = pd.concat([dg10_dates[["site_id"]].reset_index(drop=True), dg10_expanded.reset_index(drop=True)], axis=1)
    # Merge on site_id (Site_ID in df_out may be 'site_id' column)
    if "site_id" in df_out.columns:
        df_out = df_out.merge(dg10_combined, left_on="site_id", right_on="site_id", how="left")
    else:
        # fallback: try merging on site id column name variations
        df_out = df_out.merge(dg10_combined, left_on="site_id", right_on="site_id", how="left")
else:
    # ensure no KeyError for later access: create empty dg_date_0 column
    df_out["dg_date_0"] = np.nan

# ---------- Justification ----------
df_out["justification"] = np.select(
    [
        (df_out["matching_rh"] == "No") & (df_out.get("dg_date_0").notna()),
        (df_out["matching_rh"] == "Yes") & (df_out.get("dg_date_0").notna()),
    ],
    [
        "False alarm",
        "Justify continued DGRH>10"
    ],
    default=""
)

# ---------- Corrected Category_of_Alarm (only when matching_rh == "No") ----------
df_out["category_of_alarm"] = np.select(
    [
        (df_out["matching_rh"] == "No") & (df_out["claimed_rh"] > df_out.get("genset_rh", 0)),
        (df_out["matching_rh"] == "No") & (df_out["claimed_rh"] <= df_out.get("genset_rh", 0)),
    ],
    [
        "Alarm not trigger",
        "False alarm Trigger"
    ],
    default=""
)

progress_bar.progress(85)
progress_text.info("Step 5/5 — Calculating KPIs and preparing outputs.")
time.sleep(0.15)

# ---------- Format columns for display (but keep numeric behind scenes) ----------
df_out_display = df_out.copy()
df_out_display["grid_availability_pct"] = df_out_display["grid_availability_pct"].round(2).astype(str) + "%"
df_out_display["rh_difference"] = df_out_display["rh_difference"].round(2)
df_out_display["pct_of_rh_difference"] = df_out_display["pct_of_rh_difference"].round(2).astype(str) + "%"

# ---------- KPI calculations ----------
total_sites = df_out["__site_key__"].nunique() if "__site_key__" in df_out.columns else df_out["site_id"].nunique()

claimed_match_count = df_out.loc[df_out["matching_rh"] == "Yes", "__site_key__"].nunique() if "__site_key__" in df_out.columns else df_out.loc[df_out["matching_rh"] == "Yes", "site_id"].nunique()
alarm_not_trigger_count = df_out.loc[(df_out["matching_rh"]=="No") & (df_out["category_of_alarm"]=="Alarm not trigger"), "__site_key__"].nunique() if "__site_key__" in df_out.columns else df_out.loc[(df_out["matching_rh"]=="No") & (df_out["category_of_alarm"]=="Alarm not trigger"), "site_id"].nunique()
false_alarm_trigger_count = df_out.loc[(df_out["matching_rh"]=="No") & (df_out["category_of_alarm"]=="False alarm Trigger"), "__site_key__"].nunique() if "__site_key__" in df_out.columns else df_out.loc[(df_out["matching_rh"]=="No") & (df_out["category_of_alarm"]=="False alarm Trigger"), "site_id"].nunique()
continued_dgrh10_count = df_out.loc[df_out["justification"] == "Justify continued DGRH>10", "__site_key__"].nunique() if "__site_key__" in df_out.columns else df_out.loc[df_out["justification"] == "Justify continued DGRH>10", "site_id"].nunique()
avg_dgrh_gt2_count = df_out.loc[df_out["average_dgrh"] > 2, "__site_key__"].nunique() if "__site_key__" in df_out.columns else df_out.loc[df_out["average_dgrh"] > 2, "site_id"].nunique()

# percent KPIs
claimed_matching_rate_pct = round((claimed_match_count / total_sites) * 100, 2) if total_sites else 0
alarm_not_trigger_pct = round((alarm_not_trigger_count / total_sites) * 100, 2) if total_sites else 0
false_alarm_trigger_pct = round((false_alarm_trigger_count / total_sites) * 100, 2) if total_sites else 0
avg_dgrh_gt2_pct = round((avg_dgrh_gt2_count / total_sites) * 100, 2) if total_sites else 0

progress_bar.progress(100)
progress_text.success("All steps completed ✅")

# ---------- Free some memory (drop large intermediates if present) ----------
try:
    del df_all_list, df_all, merged
except Exception:
    pass

# ---------- Tabs: Raw, Summary, KPI ----------
tab1, tab2, tab3 = st.tabs(["📄 Raw Table", "📘 Summary Table", "📊 KPI Analysis"])

with tab1:
    st.subheader("Raw Data (alarms inside the refuelling window)")
    st.caption("Filtered alarm rows used in calculations (DG alarms flagged).")
    st.dataframe(raw.reset_index(drop=True), use_container_width=True)
    raw_csv = raw.reset_index(drop=True).to_csv(index=False).encode()
    st.download_button("⬇️ Download Raw CSV", raw_csv, file_name=f"DG_Raw_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")

with tab2:
    st.subheader("Summary Table")
    st.caption("Merged summary with calculated metrics (Average DGRH, Matching_RH, Category_of_Alarm, etc.)")
    st.dataframe(df_out_display.reset_index(drop=True), use_container_width=True)
    summary_csv = df_out.reset_index(drop=True).to_csv(index=False).encode()
    st.download_button("⬇️ Download Summary CSV", summary_csv, file_name=f"DG_Summary_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")

with tab3:
    st.subheader("KPI Analysis — Diesel Generator Run Hour Analysis")
    st.markdown("#### Overall KPIs")
    # Render KPI cards (each with its own download)
    # KPI 1: Claimed Matching Rate
    df_kpi1 = df_out[df_out["matching_rh"] == "Yes"].copy()
    render_kpi_card(
        "Claimed Matching Rate (%)",
        f"{claimed_matching_rate_pct}%",
        claimed_matching_rate_pct,
        f"{claimed_match_count}/{total_sites} sites matched",
        df_kpi1,
        key="kpi1"
    )

    # KPI 2: Alarm not trigger
    df_kpi2 = df_out[(df_out["matching_rh"]=="No") & (df_out["category_of_alarm"]=="Alarm not trigger")].copy()
    render_kpi_card(
        "Alarm not trigger (%)",
        f"{alarm_not_trigger_pct}%",
        alarm_not_trigger_pct,
        f"{alarm_not_trigger_count}/{total_sites} sites",
        df_kpi2,
        key="kpi2"
    )

    # KPI 3: False alarm Trigger
    df_kpi3 = df_out[(df_out["matching_rh"]=="No") & (df_out["category_of_alarm"]=="False alarm Trigger")].copy()
    render_kpi_card(
        "False alarm Trigger (%)",
        f"{false_alarm_trigger_pct}%",
        false_alarm_trigger_pct,
        f"{false_alarm_trigger_count}/{total_sites} sites",
        df_kpi3,
        key="kpi3"
    )

    # KPI 4: Continued DGRH>10 (count)
    df_kpi4 = df_out[df_out["justification"] == "Justify continued DGRH>10"].copy()
    render_kpi_card(
        "Continued DGRH>10 (count)",
        f"{continued_dgrh10_count}",
        continued_dgrh10_count,
        "Sites with continued DGRH >10 justification",
        df_kpi4,
        key="kpi4"
    )

    # KPI 5: Average DGRH>2 (%)
    df_kpi5 = df_out[df_out["average_dgrh"] > 2].copy()
    render_kpi_card(
        "Average DGRH>2 (%)",
        f"{avg_dgrh_gt2_pct}%",
        avg_dgrh_gt2_pct,
        f"{avg_dgrh_gt2_count}/{total_sites} sites",
        df_kpi5,
        key="kpi5"
    )

    st.markdown("---")
    st.markdown("**KPI Notes:** Each KPI box has a download button to export the subset behind that KPI. Downloads are generated on demand and do not require a full page refresh.")

# ---------- Footer / recommendations ----------
st.markdown("---")
st.markdown("**Notes & Recommendations:**")
st.markdown("""
- If your main dataset is very large (>100k rows), consider uploading a reduced file or using sampling for quick analysis.  
- Use `usecols` when saving the source exports to keep memory usage down.  
- To speed repeated runs, consider saving uploaded files to a known path and using `@st.cache_data` read helpers (this app caches file bytes).  
- If you want the KPI cards to be fancier (SVG 3D, Lottie animation), I can add Lottie or animated SVGs next.
""")
