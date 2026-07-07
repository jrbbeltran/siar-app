#!/usr/bin/env python3
"""
siar.app — Scholarly Impact Above Replacement
Data loaded from Google Drive (improved loader)
"""

import streamlit as st
import pandas as pd
import gdown
from io import BytesIO
from datetime import datetime, timedelta
import plotly.graph_objects as go

# ============================================================
# GOOGLE DRIVE FILE IDs (from your direct links)
# ============================================================
CSII_SCORES_ID  = "1Ul593NIQhJ3yjUqs6GNEtXDOv1IRtSX3"
CSII_DATA_ID    = "1z5pswy038NH_0DG2Kt7iMT0DAd7pb4RY"
INSTITUTIONS_ID = "1KrKfJTqSRjiOEFLZHrJWiGDI6s8Xx8F0"

# ============================================================
# IMPROVED GOOGLE DRIVE LOADER
# ============================================================
@st.cache_data(show_spinner=False)
def load_csv_from_gdrive(file_id):
    """Download CSV from Google Drive using gdown (more reliable for large files)"""
    url = f"https://drive.google.com/uc?id={file_id}&export=download"
    output = BytesIO()
    gdown.download(url, output, quiet=True, fuzzy=True)
    output.seek(0)
    return pd.read_csv(output)

# ============================================================
# LOAD DATA
# ============================================================
@st.cache_data(show_spinner=False)
def load_core_data():
    scores = load_csv_from_gdrive(CSII_SCORES_ID)
    scores['author_ids'] = scores['author_ids'].astype(str)

    for col in ['first_name', 'last_name']:
        if col in scores.columns:
            scores[col] = scores[col].astype(str).str.strip()

    full = load_csv_from_gdrive(CSII_DATA_ID)
    full['author_ids'] = full['author_ids'].astype(str)
    full['coverDate'] = pd.to_datetime(full['coverDate'], format='%m/%d/%Y', errors='coerce')

    inst = load_csv_from_gdrive(INSTITUTIONS_ID)
    return scores, full, inst

# ============================================================
# SIAR HELPER FUNCTIONS
# ============================================================
def calculate_h_index(citation_list):
    if not citation_list:
        return 0
    cites = sorted([int(c) for c in citation_list if pd.notna(c) and c > 0], reverse=True)
    h = 0
    for i, c in enumerate(cites):
        if c >= (i + 1):
            h = i + 1
        else:
            break
    return h

def get_author_h5(author_id, full_df, end_date, years=5):
    start_date = end_date - timedelta(days=years * 365.25)
    mask = (
        (full_df['author_ids'] == str(author_id)) &
        (full_df['coverDate'] >= start_date) &
        (full_df['coverDate'] <= end_date)
    )
    cites = full_df.loc[mask, 'citedby_count'].tolist()
    return calculate_h_index(cites)

def calculate_siar(h5_value, replacement_level, points_per_win=10):
    if pd.isna(h5_value):
        return 0.0
    return max(0.0, (h5_value - replacement_level) / points_per_win)

def get_interpretation(siar_value):
    if siar_value >= 6:
        return "MVP-caliber impact"
    elif siar_value >= 4:
        return "All-Star level"
    elif siar_value >= 2:
        return "Solid starter"
    elif siar_value > 0:
        return "Above replacement"
    else:
        return "At or below replacement level"

def create_siar_gauge(siar_value, max_value=8.0):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(siar_value, 2),
        title={'text': "SIAR"},
        gauge={'axis': {'range': [0, max_value]}, 'bar': {'color': "#1f77b4"}},
        number={'font': {'size': 40}}
    ))
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=20, b=10))
    return fig

# ============================================================
# STREAMLIT UI
# ============================================================
st.set_page_config(page_title="siar.app", page_icon="📈", layout="wide")

st.markdown('<p style="font-size:2.1rem;font-weight:700;color:#1f77b4">siar.app</p>', unsafe_allow_html=True)
st.caption("Scholarly Impact Above Replacement • Data from Google Drive")

try:
    scores_df, full_df, inst_df = load_core_data()
except Exception as e:
    st.error("Failed to load data from Google Drive.")
    st.info("Please make sure the files are shared as 'Anyone with the link' and redeploy.")
    st.stop()

# Sidebar
with st.sidebar:
    rl = st.slider("Replacement Level (h₅)", 0, 25, 8)
    points_per_win = st.slider("h-points per win", 5, 15, 10)
    window_years = st.slider("Years in window", 3, 10, 5)
    end_date = st.date_input("End date", value=datetime(2026, 7, 7))

tab1, tab2, tab3 = st.tabs(["Author SIAR", "Institution", "Methodology"])

with tab1:
    st.subheader("Author SIAR Lookup")
    search_id = st.text_input("author_id (recommended)", placeholder="e.g. 6506343587")
    search_name = st.text_input("or Name", placeholder="e.g. Aguinis")

    if st.button("Calculate SIAR", type="primary"):
        author_row = None
        if search_id:
            author_row = scores_df[scores_df['author_ids'] == search_id.strip()]
        elif search_name:
            parts = search_name.strip().lower().split()
            if len(parts) == 1:
                author_row = scores_df[scores_df['last_name'].str.lower().str.contains(parts[0], na=False)]
            else:
                author_row = scores_df[
                    (scores_df['first_name'].str.lower().str.contains(parts[0], na=False)) &
                    (scores_df['last_name'].str.lower().str.contains(parts[-1], na=False))
                ]

        if author_row is None or author_row.empty:
            st.warning("No match found. Try exact author_id.")
        else:
            row = author_row.iloc[0]
            author_id = str(row['author_ids'])
            all_time_h = int(row['h_index'])
            full_name = f"{row.get('first_name','')} {row.get('last_name','')}".strip()

            with st.spinner("Calculating..."):
                h5 = get_author_h5(author_id, full_df, pd.Timestamp(end_date), window_years)
            siar = calculate_siar(h5, rl, points_per_win)

            st.success(f"**{full_name}** (author_id: {author_id})")
            c1, c2, c3 = st.columns(3)
            c1.metric("All-time h", all_time_h)
            c2.metric(f"{window_years}y h₅", h5)
            c3.metric("SIAR", f"{siar:.2f}")

            st.plotly_chart(create_siar_gauge(siar), use_container_width=True)
            st.write(f"**Interpretation:** {get_interpretation(siar)}")

with tab2:
    st.info("Institution-level dashboard coming in next version.")

with tab3:
    st.markdown("""
    **SIAR** = max(0, (h₅ − RL) / s)
    
    - **h₅** = 5-year contextualized h-index
    - **RL** = Replacement Level  
    - **s** = h-points per SIAR win
    """)

st.caption("siar.app • CSII 2.0 • Academic & evaluative use only")
