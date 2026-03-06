"""
THE MIGRATION - PRODUCTION MARKETING INTELLIGENCE DASHBOARD
Single-file consolidated deployment for Streamlit Community Cloud.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import asyncio
from datetime import datetime, date, timedelta
import json
import traceback
import os
import sys

# Import Async Clients
from ghl_async_client import ghl_client
from meta_async_client import fetch_meta_data
from ga4_async_client import fetch_ga4_data
from gsc_async_client import fetch_gsc_data
import statsmodels.api as sm
import pytz

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="The Migration | Marketing Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login_gate():
    if not st.session_state.authenticated:
        # Try to get credentials from secrets, or use defaults for local testing
        try:
            auth_user = st.secrets["auth"]["username"]
            auth_pass = st.secrets["auth"]["password"]
        except:
            # Fallback for local testing
            auth_user = "themigration"
            auth_pass = "1900clients"
            
        st.markdown("<div style='text-align: center; padding-top: 100px;'>", unsafe_allow_html=True)
        st.title("🔐 Marketing Intelligence Login")
        user = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        if st.button("Login"):
            if user == auth_user and pw == auth_pass:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid credentials")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

login_gate()

# --- THEME MANAGEMENT ---
if "theme_choice" not in st.session_state:
    st.session_state.theme_choice = "Dark"

with st.sidebar:
    st.markdown("""
        <div style="padding: 0.5rem 0 1.5rem; border-bottom: 1px solid #2d2f31; margin-bottom: 1.5rem;">
            <span style="color: white; font-weight: bold; font-size: 1.5rem;">The Migration</span>
        </div>
    """, unsafe_allow_html=True)
    
    # Global Date Filter
    # Default to Nov 1st 2025 as per project history
    default_start = date(2025, 11, 1)
    default_end = date.today()
    date_range = st.date_input("Select Range", [default_start, default_end])
    
    st.markdown("<div style='margin-top: auto; padding-top: 1rem; border-top: 1px solid #2d2f31;'></div>", unsafe_allow_html=True)
    choice = st.radio("Appearance", ["Dark", "Light"], index=0 if st.session_state.theme_choice == "Dark" else 1)
    if choice != st.session_state.theme_choice:
        st.session_state.theme_choice = choice
        st.rerun()

# --- THEME VARIABLES ---
if st.session_state.theme_choice == "Dark":
    bg_color, surface_color, text_color = "#0f172a", "#1e293b", "#f8fafc"
    secondary_text, accent, border_color = "#94a3b8", "#2dd4bf", "#334155"
    table_bg, chart_bg, plotly_template = "#000000", "#1e293b", "plotly_dark"
    card_shadow = "0 10px 15px -3px rgba(0,0,0,0.3)"
    chart_text_color = "#f8fafc"
else:
    bg_color, surface_color, text_color = "#f1f5f9", "#ffffff", "#000000"
    secondary_text, accent, border_color = "#475569", "#0d9488", "#cbd5e1"
    table_bg, chart_bg, plotly_template = "#ffffff", "#ffffff", "plotly_white"
    card_shadow = "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
    chart_text_color = "#000000"

# --- CUSTOM CSS ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif !important; color: {text_color} !important; }}
    .stApp {{ background: {bg_color}; color: {text_color}; }}
    .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stText {{ color: {text_color} !important; }}
    
    /* Brand Header */
    .brand-header {{
        background: {accent};
        padding: 1.5rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: {card_shadow};
        border-left: 6px solid #1a1c1e;
    }}
    .brand-header h1 {{ color: white !important; font-size: 2.2rem; margin: 0; font-weight: 700; }}
    
    /* Tabs */
    div[data-baseweb="tab-list"] button p {{ color: {secondary_text} !important; font-weight: 500; font-size: 0.9rem; }}
    div[data-baseweb="tab-list"] button[aria-selected="true"] p {{ color: {text_color} !important; font-weight: 700; }}
    div[data-baseweb="tab-list"] button[aria-selected="true"] {{ border-bottom: 2px solid {accent} !important; }}
    
    /* Tables */
    [data-testid="stDataFrame"] {{ background-color: {table_bg} !important; border-radius: 8px; }}
    [data-testid="stDataFrame"] div[role="columnheader"] p {{
        color: {text_color} !important;
        font-weight: 700 !important;
    }}
    [data-testid="stDataFrame"] div[role="columnheader"] {{
        background-color: {surface_color} !important;
    }}
    
    /* Subheaders */
    .stSubheader > div::after {{
        content: '';
        display: block;
        height: 2px;
        width: 32px;
        background: {accent};
        border-radius: 2px;
        margin-top: 6px;
    }}
    </style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
def okr_scorecard(label, value, delta=None, color="#6366f1"):
    delta_html = f'<span style="color: #10b981; font-size: 0.8rem; font-weight: 600; margin-left: 8px;">↑ {delta}</span>' if delta else ""
    html = f'''
    <div style="background: {surface_color}; padding: 1.5rem; border-radius: 16px; border: 1px solid {border_color}; box-shadow: {card_shadow}; margin-bottom: 1rem;">
        <div style="color: {secondary_text}; font-size: 0.72rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.1em; margin-bottom: 4px;">{label}</div>
        <div style="color: {text_color}; font-size: 1.8rem; font-weight: 700; display: flex; align-items: baseline;">{value}{delta_html}</div>
        <div style="width: 30%; height: 4px; background: {color}; margin-top: 1rem; border-radius: 10px; opacity: 0.8;"></div>
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)

def apply_chart_style(fig):
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, sans-serif", color=text_color, size=12),
        template=plotly_template,
        margin=dict(l=20, r=20, t=40, b=20),
        hoverlabel=dict(bgcolor=surface_color, font_size=13),
        colorway=[accent, "#8b5cfc", "#3b82f6", "#f59e0b"]
    )
    fig.update_xaxes(showgrid=False, linecolor=border_color)
    fig.update_yaxes(showgrid=True, gridcolor=border_color, zeroline=False)
    return fig

# --- DATA ORCHESTRATION ---
@st.cache_data(ttl=900)
def load_all_intelligence(start_date, end_date):
    """
    Consolidated async fetcher. This runs all API clients in parallel
    using an event loop created within the Streamlit thread.
    """
    # Convert dates to strings for API compatibility
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    print(f"LOADER DEBUG: Requesting data for range {start_str} to {end_str}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def fetch_everything():
        # Reset specific global client sessions so they attach to this new event loop
        ghl_client._session = None
        from meta_async_client import meta_client
        meta_client._session = None
        
        # Fetching tasks
        tasks = [
            ghl_client.fetch_all_data(start_str, end_str),
            fetch_meta_data(start_str, end_str),
            fetch_ga4_data(start_str, end_str),
            fetch_gsc_data(start_str, end_str)
        ]
        # return_exceptions=True prevents one failing service from crashing the whole sync
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    try:
        results = loop.run_until_complete(fetch_everything())
        
        # Process results and log any errors
        processed = []
        services = ["GHL", "Meta", "GA4", "Search Console"]
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                # Special handling for Meta Ads if country breakdown fails
                if services[i] == "Meta" and "country" in str(res).lower():
                    st.warning(f"⚠️ Meta Ads Sync limited: Country breakdown failed. Retrying without breakdown.")
                    try:
                        # Attempt to refetch Meta data without country breakdown
                        meta_fallback_data = loop.run_until_complete(fetch_meta_data(start_str, end_str, breakdown=None))
                        processed.append(meta_fallback_data)
                    except Exception as fallback_e:
                        st.warning(f"⚠️ Meta Ads Sync limited: Fallback without breakdown also failed: {str(fallback_e)}")
                        processed.append({}) # Provide empty dict for failed service
                else:
                    st.warning(f"⚠️ {services[i]} Sync limited: {str(res)}")
                    processed.append({}) # Provide empty dict for failed service
            else:
                processed.append(res)
                
        # The GHL client (ghl_async_client) already returns processed 'opportunities'
        # but leaves contacts relatively raw. Let's ONLY merge contacts here.
        ghl_raw = processed[0]
        if ghl_raw and isinstance(ghl_raw, dict) and "contacts" in ghl_raw:
            from ghl_async_client import merge_contact_data
            ghl_raw["contacts"] = merge_contact_data(
                ghl_raw["contacts"], ghl_raw["opportunities"], 
                ghl_raw["appointments"], ghl_raw["pipelines"], ghl_raw["users"]
            )
            processed[0] = ghl_raw
                
        return {
            "ghl": processed[0], 
            "meta": processed[1], 
            "ga4": processed[2], 
            "gsc": processed[3]
        }
    except Exception as e:
        error_details = traceback.format_exc()
        st.error(f"Critical Intelligence Sync Failure: {e}")
        with st.expander("Show Technical Details"):
            st.code(error_details)
        return None
    finally:
        async def cleanup():
            if getattr(ghl_client, '_session', None) and not ghl_client._session.closed:
                await ghl_client._session.close()
            from meta_async_client import meta_client
            if getattr(meta_client, '_session', None) and not meta_client._session.closed:
                await meta_client._session.close()
                
        try:
            loop.run_until_complete(cleanup())
        except Exception:
            pass
        loop.close()

# --- MAIN LOAD ---
if len(date_range) == 2:
    with st.spinner("Synchronizing Global Marketing Intelligence..."):
        all_data = load_all_intelligence(date_range[0], date_range[1])
else:
    st.warning("Please select a valid date range.")
    st.stop()

if not all_data:
    st.stop()

# --- CONTENT RENDERING ---
st.markdown("""
    <div class="brand-header">
        <h1>Marketing Performance Intelligence</h1>
    </div>
""", unsafe_allow_html=True)

def style_df(df, bold=False):
    props = {'background-color': table_bg, 'color': text_color, 'border-color': border_color}
    if bold: props['font-weight'] = 'bold'
    if hasattr(df, 'style'):
        return df.style.set_properties(**props)
    return df

# --- NAVIGATION ---
tab_titles = [
    "🎯 Our Vision", "📊 Ads & Creatives", "📈 Traffic Behavior", 
    "🔍 SEO Performance", "💼 Pipeline Analysis", "👥 Attribution Analysis", "👨‍🏫 Consultant Capacity"
]

# Persistent Tab Selection
# We use st.tabs with a key, which Streamlit uses to remember selection across reruns
tabs = st.tabs(tab_titles)
    
STAGE_ORDER = [
    "New Lead", "Qualifier", "Pre Sales (1)", "Pre Sales (2)",
    "Booking Link Shared", "Appointment Booked", "Post Consultation",
    "No Show", "Initial Requested", "Initial Received", "COE Received", "Won"
]

# --- GHL DATA PROCESSING ---
ghl = all_data["ghl"]

opps = pd.DataFrame(ghl.get('opportunities', []))
if not opps.empty and 'created_date' in opps.columns:
    opps['created_date'] = pd.to_datetime(opps['created_date']).dt.date
    opps = opps[(opps['created_date'] >= date_range[0]) & (opps['created_date'] <= date_range[1])].copy()
    
contacts = pd.DataFrame(ghl.get('contacts', []))
if not contacts.empty and 'contact_created' in contacts.columns:
    contacts['contact_created'] = pd.to_datetime(contacts['contact_created']).dt.date
    contacts = contacts[(contacts['contact_created'] >= date_range[0]) & (contacts['contact_created'] <= date_range[1])].copy()

consultant_today = ghl.get('consultants_today', [])
consultant_weekly = ghl.get('consultants_weekly', [])

# Map GHL columns
if not opps.empty:
    mapping = {
        'value': 'Opportunity Value',
        'status': 'Status',
        'pipeline': 'Pipeline',
        'stage': 'Stage',
        'owner': 'Lead Owner',
        'source': 'Lead Source',
        'contact_name': 'Contact Name',
        'opportunity_name': 'Opportunity Name',
        'created_date': 'created_date'
    }
    # Safe rename logic
    if hasattr(opps, 'columns') and opps.columns is not None:
        safe_mapping = {k: v for k, v in mapping.items() if k in opps.columns}
        opps.rename(columns=safe_mapping, inplace=True)
            
        # Ensure Country and City exist (may be mapped from unified API or merged data)
        if 'Country' not in opps.columns and 'country' in opps.columns:
            opps.rename(columns={'country': 'Country'}, inplace=True)
        if 'City' not in opps.columns and 'city' in opps.columns:
            opps.rename(columns={'city': 'City'}, inplace=True)
            
        def get_stage_pct(s):
            try:
                if s in STAGE_ORDER:
                    return (STAGE_ORDER.index(s) / (len(STAGE_ORDER) - 1)) * 100
                return 0
            except: return 0
            
        if 'Stage' in opps.columns:
            opps['Stage Percentage'] = opps['Stage'].apply(get_stage_pct)

# --- TAB 0: OUR VISION ---
with tabs[0]:
    st.subheader("Strategic Alignment")
    c1, c2, c3, c4 = st.columns(4)
    with c1: okr_scorecard("Current Clients", "344")
    with c2: okr_scorecard("Target Clients", "1,900")
    with c3: okr_scorecard("Growth Required", "452%")
    with c4: okr_scorecard("Cultures Connected", "6", color="#f6ad55")
    
    st.write("##")
    v1, v2 = st.columns(2)
    v1.markdown(f"<div style='border-left: 5px solid {accent}; padding: 25px; background: {surface_color}; border-radius: 12px; box-shadow: {card_shadow};'><b>VISION</b><br><small>To be the world's most trusted migration partner...</small></div>", unsafe_allow_html=True)
    v2.markdown(f"<div style='border-left: 5px solid #8b5cfc; padding: 25px; background: {surface_color}; border-radius: 12px; box-shadow: {card_shadow};'><b>MISSION</b><br><small>Solving migration challenges with transparency and accuracy...</small></div>", unsafe_allow_html=True)

# --- TAB 1: ADS & CREATIVES ---
with tabs[1]:
    meta = all_data.get("meta", {})
    df_agg_raw = pd.DataFrame(meta.get("campaigns", []))
    df_daily_raw = pd.DataFrame(meta.get("daily", []))
    
    if not df_agg_raw.empty:
        # --- TOP CONTROL BAR ---
        all_meta_countries = sorted(df_agg_raw['Country'].unique()) if 'Country' in df_agg_raw.columns else []
        ctrl_c1, ctrl_c2 = st.columns([3, 1])
        with ctrl_c1:
            selected_meta_countries = st.multiselect("Filter by Country", all_meta_countries, default=all_meta_countries[:3] if len(all_meta_countries) > 3 else all_meta_countries, key="meta_country_filt") if all_meta_countries else []
        with ctrl_c2:
            meta_comparison_mode = st.toggle("Side-by-Side Comparison", key="meta_comp_toggle")

        df_agg_filt = df_agg_raw[df_agg_raw['Country'].isin(selected_meta_countries)].copy() if selected_meta_countries else df_agg_raw.copy()
        
        # Robustness: If filtered data is empty but raw data is not, fallback to all (prevents disappearance on date change)
        if df_agg_filt.empty and not df_agg_raw.empty:
            df_agg_filt = df_agg_raw.copy()
        
        if df_agg_filt.empty:
            st.info(f"No Meta data matches the selected Country filter: {selected_meta_countries}")
            
        def render_meta_content(df_f, df_daily_f, title_prefix=""):
            # 1. Performance KPIs
            st.markdown(f"### {title_prefix} **1. Performance KPIs**")
            t_spend = df_f['Amount spent'].sum() if 'Amount spent' in df_f.columns else 0
            t_leads = df_f['Results'].sum() if 'Results' in df_f.columns else 0
            avg_cpl = t_spend / t_leads if t_leads > 0 else 0
            t_impr = df_f['Impressions'].sum() if 'Impressions' in df_f.columns else 0
            t_links = df_f['Link clicks'].sum() if 'Link clicks' in df_f.columns else 0
            t_outbound = df_f['Outbound clicks'].sum() if 'Outbound clicks' in df_f.columns else 0
            avg_ctr_link = df_f['CTR (link click-through rate)'].mean() if 'CTR (link click-through rate)' in df_f.columns else 0
            avg_ctr_out = (t_outbound / t_impr * 100) if t_impr > 0 else 0
            
            k1, k2, k3 = st.columns(3)
            with k1: okr_scorecard("Total Spend", f"${t_spend:,.0f}")
            with k2: okr_scorecard("Total Leads", f"{int(t_leads):,}")
            with k3: okr_scorecard("Avg. CPL", f"${avg_cpl:.2f}")
            
            p4, p5, p6 = st.columns(3)
            with p4: okr_scorecard("Link Clicks", f"{int(t_links):,}")
            with p5: okr_scorecard("Outbound CTR", f"{avg_ctr_out:.2f}%")
            with p6: okr_scorecard("Link CTR", f"{avg_ctr_link:.2f}%")

            st.divider()

            # 2. Creative Engagement
            st.markdown(f"### {title_prefix} **2. Creative Engagement (Hook & Hold)**")
            hook_rate = (df_f['3s Hold'].sum() / t_impr * 100) if t_impr > 0 and '3s Hold' in df_f.columns else 0
            hold_rate = (df_f['Thruplays'].sum() / t_impr * 100) if t_impr > 0 and 'Thruplays' in df_f.columns else 0
            vh1, vh2 = st.columns(2)
            with vh1: okr_scorecard("Hook Rate (3s/Impr)", f"{hook_rate:.1f}%")
            with vh2: okr_scorecard("Hold Rate (Thru/Impr)", f"{hold_rate:.1f}%")

            st.divider()

            # 3. Video Retention Pipeline
            st.markdown(f"### {title_prefix} **3. Video Retention Pipeline**")
            v_metrics = ['3s Hold', '50% Hook', '95% Hook', 'Thruplays']
            v_counts = [df_f[m].sum() if m in df_f.columns else 0 for m in v_metrics]
            fig_hook = px.bar(x=v_counts, y=v_metrics, orientation='h', title=f"{title_prefix} Retention Pipeline", color_discrete_sequence=[accent])
            st.plotly_chart(apply_chart_style(fig_hook), use_container_width=True)

            st.divider()

            # 4. Campaign Performance Analysis
            st.markdown(f"### {title_prefix} **4. Campaign Performance Analysis**")
            if 'Frequency' in df_f.columns:
                df_fat = df_f.copy()
                df_fat['Frequency'] = pd.to_numeric(df_fat['Frequency'], errors='coerce')
                df_fat = df_fat[df_fat['Frequency'] > 0]
                if len(df_fat) > 1:
                    fig_fat = px.scatter(df_fat, x="Frequency", y="CTR (link click-through rate)", 
                                        size="Amount spent", color="Campaign", hover_name="Campaign",
                                        trendline="ols", trendline_color_override="red",
                                        title=f"{title_prefix} CTR% vs. Frequency Fatigue")
                    st.plotly_chart(apply_chart_style(fig_fat), use_container_width=True)
                else:
                    st.info("Insufficient data points (min 2) for frequency fatigue trendline analysis.")

            st.divider()

            # 5. Strategic Performance Correlation
            st.markdown(f"### {title_prefix} **5. Strategic Performance Correlation**")
            df_core = df_f.copy()
            df_core['Result Rate (%)'] = (df_core['Results'] / df_core['Impressions'] * 100).fillna(0)
            fig_strat = px.scatter(df_core, x="CTR (link click-through rate)", y="Result Rate (%)",
                                size="Results", color="Campaign", hover_name="Campaign",
                                title=f"{title_prefix} Messaging Relevance vs. Intensity")
            st.plotly_chart(apply_chart_style(fig_strat), use_container_width=True)

            st.divider()

            # 6. Landing Page Health
            st.markdown(f"### {title_prefix} **6. Landing Page Health**")
            t_lp = df_f['Landing page views'].sum() if 'Landing page views' in df_f.columns else 0
            drop_off = (1 - t_lp / t_links) * 100 if t_links > 0 else 0
            l_col1, l_col2 = st.columns([1, 2])
            with l_col1:
                okr_scorecard("Drop-off Rate", f"{drop_off:.1f}%", color="#ef4444" if drop_off > 60 else "#10b981")
            with l_col2:
                if drop_off > 60: st.warning("⚠️ Warning: High drop-off rate detected. Potential relevance or speed issue.")
                else: st.success("✅ LP health is looking good.")

            st.divider()

            # 7. Conversion Type Breakdown
            st.markdown(f"### {title_prefix} **7. Conversion Type Breakdown**")
            with st.expander(f"🔍 View All Conversion Actions ({title_prefix.strip()})", expanded=False):
                all_actions = {}
                if '_actions' in df_f.columns:
                    for map_data in df_f['_actions']:
                        if isinstance(map_data, dict):
                            for k, v in map_data.items(): all_actions[k] = all_actions.get(k, 0) + v
                if all_actions:
                    df_action = pd.DataFrame(list(all_actions.items()), columns=['Conversion Type', 'Count']).sort_values('Count', ascending=False)
                    st.dataframe(style_df(df_action), use_container_width=True, hide_index=True)
                else: st.info("No action data found.")

            st.divider()

            # 8. Meta Campaigns Table
            st.markdown(f"### {title_prefix} **8. Meta Campaigns**")
            with st.expander(f"📂 View Detailed Campaigns ({title_prefix.strip()})", expanded=False if title_prefix else True):
                agg_rules = {
                    'Amount spent': 'sum', 'Results': 'sum', 'Impressions': 'sum', 
                    'Link clicks': 'sum', '3s Hold': 'sum', 'Thruplays': 'sum',
                    'CTR (link click-through rate)': 'mean', 'CTR (all)': 'mean', 'Frequency': 'mean'
                }
                found_cols = [c for c in agg_rules.keys() if c in df_f.columns]
                # Ensure Country is in grouping if it exists
                group_cols = ['Campaign']
                if 'Country' in df_f.columns: group_cols.append('Country')
                
                df_final = df_f.groupby(group_cols).agg({c: agg_rules[c] for c in found_cols}).reset_index()
                st.dataframe(style_df(df_final, bold=True), use_container_width=True, hide_index=True)
                csv = df_final.to_csv(index=False).encode('utf-8')
                st.download_button(f"📥 Download {title_prefix.strip()} Report", data=csv, file_name=f"meta_report_{title_prefix.strip()}.csv", key=f"dl_{title_prefix}")

        if meta_comparison_mode and len(selected_meta_countries) == 2:
            mc1, mc2 = selected_meta_countries[0], selected_meta_countries[1]
            st.markdown(f"## ⚔️ Comparison: {mc1} vs {mc2}")
            m_comp_col1, m_comp_col2 = st.columns(2)
            with m_comp_col1:
                df1 = df_agg_raw[df_agg_raw['Country']==mc1]
                dd1 = df_daily_raw[df_daily_raw['Country']==mc1] if 'Country' in df_daily_raw.columns else pd.DataFrame()
                render_meta_content(df1, dd1, f"📊 {mc1}")
            with m_comp_col2:
                df2 = df_agg_raw[df_agg_raw['Country']==mc2]
                dd2 = df_daily_raw[df_daily_raw['Country']==mc2] if 'Country' in df_daily_raw.columns else pd.DataFrame()
                render_meta_content(df2, dd2, f"📊 {mc2}")
        else:
            # Fallback for daily data as well
            df_daily_filt = df_daily_raw[df_daily_raw['Country'].isin(selected_meta_countries)] if 'Country' in df_daily_raw.columns and selected_meta_countries else df_daily_raw
            if df_daily_filt.empty and not df_daily_raw.empty:
                df_daily_filt = df_daily_raw.copy()
                
            render_meta_content(df_agg_filt, df_daily_filt)
            
    else:
        st.info("No Meta Ads campaign data found.")
        with st.expander("Debug Details"):
            st.write("Meta Object Status:", "Present" if meta else "Empty")
            if not meta:
                st.write("Check Meta Access Token in secrets or meta_async_client.py")
            st.json(meta)

# --- TAB 2: TRAFFIC BEHAVIOUR ---
with tabs[2]:
    ga4 = all_data.get("ga4", {})
    if ga4 and isinstance(ga4, dict) and "daily" in ga4:
        df_daily_raw = pd.DataFrame(ga4["daily"])
        
        # --- GEO FILTERS ---
        with st.expander("🌍 Geo Filters (GA4)", expanded=False):
            f_ga1, f_ga2 = st.columns([3, 1])
            with f_ga1:
                all_ga_countries = sorted(df_daily_raw['Country'].unique()) if 'Country' in df_daily_raw.columns else []
                sel_ga_countries = st.multiselect("Filter GA4 by Country", all_ga_countries, default=all_ga_countries[:3] if all_ga_countries else [], key="ga4_c_filt")
            with f_ga2:
                ga4_comparison_mode = st.toggle("Side-by-Side Comparison", key="ga4_comp_toggle")

        def render_ga4_content(countries_to_show, title_prefix=""):
            df_d = df_daily_raw.copy()
            if countries_to_show:
                df_d = df_d[df_d['Country'].isin(countries_to_show)]
            
            # 1. Engagement Overview
            st.markdown(f"### {title_prefix} **1. Engagement Overview**")
            t_active = df_d["Active Users"].sum()
            t_sessions = df_d["Sessions"].sum()
            t_views = df_d["Views"].sum()
            t_events = df_d["Key Events"].sum()
            a_bounce = df_d["Bounce Rate"].mean()
            
            k_cols = st.columns(5)
            with k_cols[0]: okr_scorecard("Active Users", f"{t_active:,}")
            with k_cols[1]: okr_scorecard("Sessions", f"{t_sessions:,}")
            with k_cols[2]: okr_scorecard("Views", f"{t_views:,}")
            with k_cols[3]: okr_scorecard("Key Events", f"{t_events:,}", color="#10b981")
            with k_cols[4]: okr_scorecard("Bounce Rate", f"{(a_bounce or 0)*100:.1f}%", color="#ef4444")

            st.markdown(f"#### {title_prefix} **User Engagement Trend**")
            df_d['Date'] = pd.to_datetime(df_d['Date'])
            df_d_grp = df_d.groupby('Date').sum(numeric_only=True).reset_index().sort_values('Date')
            if not df_d_grp.empty:
                # 7-day Moving Average for Smoothing
                if len(df_d_grp) >= 7:
                    df_d_grp["Smooth Users"] = df_d_grp["Active Users"].rolling(window=7, min_periods=1).mean()
                    fig_trend = px.area(df_d_grp, x='Date', y='Smooth Users', 
                                         title=f"{title_prefix} Engagement Trend (7-Day Moving Avg)", 
                                         color_discrete_sequence=["#2dd4bf"])
                    fig_trend.update_traces(line=dict(width=4, shape='spline'), fillcolor='rgba(45, 212, 191, 0.2)')
                else:
                    fig_trend = px.area(df_d_grp, x='Date', y='Active Users', 
                                         title=f"{title_prefix} Daily Active Users", 
                                         color_discrete_sequence=["#2dd4bf"])
                st.plotly_chart(apply_chart_style(fig_trend), use_container_width=True)

            st.divider()
            
            # 2. User Acquisition: Channel Trends
            st.markdown(f"### {title_prefix} **2. User Acquisition: Channel Trends**")
            if "channels" in ga4:
                df_chan = pd.DataFrame(ga4["channels"])
                if not df_chan.empty:
                    if countries_to_show:
                        df_chan = df_chan[df_chan['country'].isin(countries_to_show)]
                    df_c_grp = df_chan.groupby('channel')['sessions'].sum().reset_index().sort_values('sessions', ascending=False)
                    fig_chan = px.bar(df_c_grp, x="sessions", y="channel", orientation='h', title=f"{title_prefix} Sessions by Channel", color="sessions")
                    st.plotly_chart(apply_chart_style(fig_chan), use_container_width=True)

            # 3. Traffic by Country (Only if not in 1-country mode)
            if not countries_to_show or len(countries_to_show) > 1:
                st.divider()
                st.markdown(f"### {title_prefix} **3. Traffic by Country**")
                if "countries" in ga4:
                    df_geo = pd.DataFrame(ga4["countries"])
                    if not df_geo.empty:
                        if countries_to_show:
                            df_geo = df_geo[df_geo['country'].isin(countries_to_show)]
                        df_g = df_geo.sort_values("users", ascending=False).head(10)
                        if not df_g.empty:
                            fig_geo = px.pie(df_g, values="users", names="country", hole=0.4, title=f"{title_prefix} User Distribution")
                            st.plotly_chart(apply_chart_style(fig_geo), use_container_width=True)

            # 4. Key Events Behavior (Moving Avg)
            st.divider()
            st.markdown(f"### {title_prefix} **4. Key Events Behaviour (Trend)**")
            if not df_d_grp.empty:
                if len(df_d_grp) >= 7:
                    df_d_grp["Smooth Events"] = df_d_grp["Key Events"].rolling(window=7, min_periods=1).mean()
                    fig_key = px.area(df_d_grp, x='Date', y='Smooth Events', 
                                    title=f"{title_prefix} Key Events Trend (7-Day Moving Avg)",
                                    color_discrete_sequence=["#2dd4bf"])
                    fig_key.update_traces(line=dict(width=4, shape='spline'), fillcolor='rgba(45, 212, 191, 0.2)')
                else:
                    fig_key = px.area(df_d_grp, x='Date', y='Key Events', 
                                     title=f"{title_prefix} Daily Key Events",
                                     color_discrete_sequence=["#2dd4bf"])
                st.plotly_chart(apply_chart_style(fig_key), use_container_width=True)

            st.divider()

            # 5. Page Performance Analysis
            st.markdown(f"### {title_prefix} **5. Page Performance Analysis**")
            p1, p2 = st.columns(2) if not ga4_comparison_mode else (st.container(), st.container())
            with p1:
                st.markdown(f"#### {title_prefix} Top Page Titles")
                if "page_titles" in ga4:
                    df_t = pd.DataFrame(ga4["page_titles"])
                    if countries_to_show:
                        df_t = df_t[df_t['country'].isin(countries_to_show)] if 'country' in df_t.columns else df_t
                    if not df_t.empty and 'Page Title' in df_t.columns:
                        df_t_disp = df_t.groupby('Page Title')['Views'].sum().reset_index().sort_values('Views', ascending=False).head(15)
                        st.dataframe(style_df(df_t_disp), use_container_width=True, hide_index=True)
            with p2:
                st.markdown(f"#### {title_prefix} Top Page Paths")
                if "page_paths" in ga4:
                    df_p = pd.DataFrame(ga4["page_paths"])
                    if countries_to_show:
                        df_p = df_p[df_p['country'].isin(countries_to_show)] if 'country' in df_p.columns else df_p
                    if not df_p.empty and 'Page Path' in df_p.columns:
                        df_p_disp = df_p.groupby('Page Path')['Views'].sum().reset_index().sort_values('Views', ascending=False).head(15)
                        st.dataframe(style_df(df_p_disp), use_container_width=True, hide_index=True)

        if ga4_comparison_mode and len(sel_ga_countries) == 2:
            c1, c2 = sel_ga_countries[0], sel_ga_countries[1]
            st.markdown(f"## ⚔️ Comparison: {c1} vs {c2}")
            comp_col1, comp_col2 = st.columns(2)
            with comp_col1: render_ga4_content([c1], f"📊 {c1}")
            with comp_col2: render_ga4_content([c2], f"📊 {c2}")
        else:
            render_ga4_content(sel_ga_countries if sel_ga_countries else [])
    else:
        st.warning("⚠️ GA4 Sync limited: 403 Forbidden.")
        st.info("💡 **Resolution:** Add `ga4-monitor@ghldataset.iam.gserviceaccount.com` as a 'Viewer' in Google Analytics Admin -> Property Access Management.")
        st.info("No GA4 data found.")


# --- TAB 3: SEO PERFORMANCE ---
with tabs[3]:
    gsc = all_data.get("gsc", {})
    df_trend_raw = pd.DataFrame(gsc.get("trend", []))
    df_query_raw = pd.DataFrame(gsc.get("queries", []))
    df_pages_raw = pd.DataFrame(gsc.get("pages", []))
    
    if not df_trend_raw.empty:
        # Pre-process keys: keys format is [date/query/page, country]
        def safe_key(row, idx):
            try: return row[idx]
            except: return "unknown"
        if 'keys' in df_trend_raw.columns:
            df_trend_raw['Date'] = pd.to_datetime(df_trend_raw['keys'].apply(lambda x: safe_key(x, 0)))
            df_trend_raw['Country_Code'] = df_trend_raw['keys'].apply(lambda x: safe_key(x, 1))
        if not df_query_raw.empty and 'keys' in df_query_raw.columns:
            df_query_raw['Query'] = df_query_raw['keys'].apply(lambda x: safe_key(x, 0))
            df_query_raw['Country_Code'] = df_query_raw['keys'].apply(lambda x: safe_key(x, 1))
        if not df_pages_raw.empty and 'keys' in df_pages_raw.columns:
            df_pages_raw['Page'] = df_pages_raw['keys'].apply(lambda x: safe_key(x, 0))
            df_pages_raw['Country_Code'] = df_pages_raw['keys'].apply(lambda x: safe_key(x, 1))
        
        # --- SEO GEO FILTER ---
        with st.expander("🌍 Geo Filters (GSC)", expanded=False):
            f_gs1, f_gs2 = st.columns([3, 1])
            with f_gs1:
                all_gsc_countries = sorted(df_trend_raw['Country_Code'].unique()) if 'Country_Code' in df_trend_raw.columns else []
                sel_gsc_countries = st.multiselect("Filter SEO by Country", all_gsc_countries, default=all_gsc_countries[:3] if all_gsc_countries else [], key="gsc_c_filt")
            with f_gs2:
                seo_comparison_mode = st.toggle("Side-by-Side Comparison", key="seo_comp_toggle")

        def render_seo_content(countries_to_show, title_prefix=""):
            df_t = df_trend_raw.copy()
            if countries_to_show:
                df_t = df_t[df_t['Country_Code'].isin(countries_to_show)]
                
            # 1. Performance Overview
            st.markdown(f"### {title_prefix} **1. SEO Performance Overview**")
            t_clicks = df_t['clicks'].sum()
            t_impr = df_t['impressions'].sum()
            avg_ctr = (t_clicks / t_impr * 100) if t_impr > 0 else 0
            avg_pos = df_t['position'].mean()
            
            k_cols = st.columns(4)
            with k_cols[0]: okr_scorecard("Total Clicks", f"{t_clicks:,}")
            with k_cols[1]: okr_scorecard("Total Impressions", f"{t_impr:,}")
            with k_cols[2]: okr_scorecard("Avg. CTR", f"{avg_ctr:.2f}%")
            with k_cols[3]: okr_scorecard("Avg. Position", f"{avg_pos:.1f}", color="#8b5cfc")

            st.markdown(f"### {title_prefix} **2. SEO Performance Trend**")
            df_t_grp = df_t.groupby('Date').agg({'clicks': 'sum', 'impressions': 'sum'}).reset_index().sort_values('Date')
            if not df_t_grp.empty:
                fig_p = go.Figure()
                fig_p.add_trace(go.Scatter(x=df_t_grp['Date'], y=df_t_grp['clicks'], name="Clicks", line=dict(color=accent, width=3), fill='tozeroy'))
                fig_p.add_trace(go.Scatter(x=df_t_grp['Date'], y=df_t_grp['impressions'], name="Impressions", yaxis="y2", line=dict(color="#8b5cfc", width=2, dash='dot')))
                fig_p.update_layout(height=450, yaxis=dict(title="Clicks", color=accent), yaxis2=dict(title="Impressions", overlaying='y', side='right', color='#8b5cfc'), hovermode="x unified", legend=dict(orientation="h", y=1.2, x=0.5, xanchor='center'))
                st.plotly_chart(apply_chart_style(fig_p), use_container_width=True)

            # 3. Golden Opportunity Matrix
            st.markdown(f"### {title_prefix} **3. Golden Opportunity Matrix — Keyword Rankings**")
            df_q_local = pd.DataFrame(gsc.get("queries", []))
            if not df_q_local.empty:
                df_q_local['Query'] = df_q_local['keys'].apply(lambda x: safe_key(x, 0))
                df_q_local['Country_Code'] = df_q_local['keys'].apply(lambda x: safe_key(x, 1))
                if countries_to_show:
                    df_q_local = df_q_local[df_q_local['Country_Code'].isin(countries_to_show)]
                
                df_q_grp = df_q_local.groupby('Query').agg({'clicks': 'sum', 'impressions': 'sum', 'position': 'mean'}).reset_index()
                if not df_q_grp.empty:
                    df_q_grp['Zone'] = df_q_grp['position'].apply(lambda p: 'Top Ranking' if p < 5 else ('High Opportunity' if 5 <= p <= 15 else 'Monitoring'))
                    color_map = {'Top Ranking': '#1e3a8a', 'High Opportunity': '#d97706', 'Monitoring': '#94a3b8'}
                    
                    fig_m = px.scatter(df_q_grp, x="position", y="impressions", size="clicks", color="Zone", 
                                       hover_name="Query", height=500, color_discrete_map=color_map,
                                       labels={"position": "Avg Position", "impressions": "Impressions"})
                    
                    # Annotations from mkdashboarddf.py
                    fig_m.add_vrect(x0=0, x1=5, fillcolor="#F0F8FF", opacity=0.15, layer="below", line_width=0)
                    fig_m.add_vrect(x0=5, x1=15, fillcolor="#F7E7CE", opacity=0.2, layer="below", line_width=0, annotation_text="🎯 OPPORTUNITY ZONE", annotation_position="top left")

                    max_imp = df_q_grp['impressions'].max()
                    fig_m.add_annotation(x=2.5, y=max_imp*0.9, text="<b>MAINTAIN</b>", showarrow=False, font=dict(size=14, color="#94a3b8"), opacity=0.4)
                    fig_m.add_annotation(x=10, y=max_imp*0.9, text="<b>SCALE NOW</b>", showarrow=False, font=dict(size=14, color="#94a3b8"), opacity=0.4)
                    fig_m.add_annotation(x=25, y=max_imp*0.9, text="<b>MONITOR</b>", showarrow=False, font=dict(size=14, color="#94a3b8"), opacity=0.4)

                    fig_m.update_xaxes(autorange="reversed", showgrid=True, gridcolor=border_color)
                    fig_m.update_yaxes(showgrid=True, gridcolor=border_color)
                    fig_m.update_traces(marker=dict(line=dict(width=1, color='white'), opacity=0.8))
                    st.plotly_chart(apply_chart_style(fig_m), use_container_width=True)

            st.divider()

            # 4. Content Performance
            st.markdown(f"### {title_prefix} **4. Content Performance — Clicks vs CTR**")
            df_p_local = pd.DataFrame(gsc.get("pages", []))
            if not df_p_local.empty:
                df_p_local['Page'] = df_p_local['keys'].apply(lambda x: safe_key(x, 0))
                df_p_local['Country_Code'] = df_p_local['keys'].apply(lambda x: safe_key(x, 1))
                if countries_to_show:
                    df_p_local = df_p_local[df_p_local['Country_Code'].isin(countries_to_show)]
                df_p_grp = df_p_local.groupby('Page').agg({'clicks': 'sum'}).reset_index().sort_values('clicks', ascending=False).head(10)
                if not df_p_grp.empty:
                    fig_bar = go.Figure()
                    fig_bar.add_trace(go.Bar(
                        y=df_p_grp['Page'], x=df_p_grp['clicks'], orientation='h', name='Clicks',
                        marker=dict(
                            color=df_p_grp['clicks'],
                            colorscale=[[0, '#cffafe'], [0.5, '#3b82f6'], [1, '#10b981']],
                            line=dict(width=0)
                        ),
                        text=df_p_grp['clicks'], textposition='outside', textfont=dict(weight='bold')
                    ))
                    fig_bar.update_layout(height=450, showlegend=False, yaxis=dict(autorange="reversed"))
                    st.plotly_chart(apply_chart_style(fig_bar), use_container_width=True)

            st.divider()

            # 5. Search Console Keyword Intelligence
            st.markdown(f"### {title_prefix} **5. Search Console Keyword Intelligence**")
            if not df_q_local.empty:
                df_intel = df_q_local.groupby('Query').agg({
                    'clicks': 'sum', 'impressions': 'sum', 'ctr': 'mean', 'position': 'mean'
                }).reset_index().sort_values('clicks', ascending=False).head(20)
                df_intel['ctr'] = df_intel['ctr'] * 100
                df_intel.columns = ['Keyword', 'Clicks', 'Impressions', 'CTR (%)', 'Avg Pos']
                st.dataframe(style_df(df_intel), use_container_width=True, hide_index=True)

        if seo_comparison_mode and len(sel_gsc_countries) == 2:
            sc1, sc2 = sel_gsc_countries[0], sel_gsc_countries[1]
            st.markdown(f"## ⚔️ Comparison: {sc1} vs {sc2}")
            s_comp_col1, s_comp_col2 = st.columns(2)
            with s_comp_col1: render_seo_content([sc1], f"📊 {sc1}")
            with s_comp_col2: render_seo_content([sc2], f"📊 {sc2}")
        else:
            render_seo_content(sel_gsc_countries if sel_gsc_countries else [])
    else:
        st.warning("⚠️ SEO Sync limited: 403 User does not have sufficient permission.")
        st.info("💡 **Resolution:** Add `antigravity-fetcher@ghldataset.iam.gserviceaccount.com` as a 'Viewer' in Google Search Console → Settings → Users & Permissions for 'https://themigration.com.au/'.")


# --- TAB 4: PIPELINE ANALYSIS ---
with tabs[4]:
    if not opps.empty:
        # Ensure numeric Opportunity Value
        if 'Opportunity Value' in opps.columns:
            opps['Opportunity Value'] = pd.to_numeric(opps['Opportunity Value'], errors='coerce').fillna(0)

        # --- TOP CONTROL BAR ---
        all_pipe_countries = sorted(opps['Country'].dropna().unique()) if 'Country' in opps.columns else []
        pc1, pc2 = st.columns([3, 1])
        with pc1:
            sel_pipe_countries = st.multiselect("Filter Pipeline by Country", all_pipe_countries, default=all_pipe_countries[:3] if len(all_pipe_countries) > 3 else all_pipe_countries, key="pipe_country_filt") if all_pipe_countries else []
        with pc2:
            pipe_comparison_mode = st.toggle("Side-by-Side Comparison", key="pipe_comp_toggle")

        opps_filtered = opps[opps['Country'].isin(sel_pipe_countries)].copy() if sel_pipe_countries else opps.copy()

        def render_pipeline_content(df_f, title_prefix=""):
            st.markdown(f"<small>Records: {len(df_f)} opportunities</small>", unsafe_allow_html=True)
            st.markdown("---")

            # 1. Pipeline KPI's
            st.markdown(f"### {title_prefix} **1. Pipeline KPI's**")
            total_val = df_f['Opportunity Value'].sum() if 'Opportunity Value' in df_f.columns else 0
            l2c_open_count = 0
            if 'Pipeline' in df_f.columns and 'Status' in df_f.columns:
                l2c_open_count = len(df_f[(df_f['Pipeline'] == 'L2C - Education') & (df_f['Status'] == 'open')])

            k_cols = st.columns(3)
            with k_cols[0]: okr_scorecard("Total Opportunities", f"{len(df_f):,}")
            with k_cols[1]: okr_scorecard("Pipeline Value", f"${total_val:,.0f}", color="#10b981")
            with k_cols[2]: okr_scorecard("L2C Education (Open)", f"{l2c_open_count:,}", color="#8b5cfc")
            
            st.divider()
            
            # 2. Owner & Status Analysis
            st.markdown(f"### {title_prefix} **2. Owner Analysis**")
            col_chart1, col_chart2 = st.columns(2)
            p_colors = {'won': '#10b981', 'open': '#1e3a8a', 'lost': '#94a3b8', 'abandoned': '#64748b'}
            
            with col_chart1:
                if 'Lead Owner' in df_f.columns and 'Status' in df_f.columns:
                    owner_counts = df_f.groupby('Lead Owner').size().reset_index(name='Total').sort_values('Total', ascending=False)
                    top_15 = owner_counts.head(15)['Lead Owner'].tolist()
                    
                    df_owner = df_f.copy()
                    df_owner['Owner Display'] = df_owner['Lead Owner'].apply(lambda x: "".join([n[0] for n in str(x).split()]) if str(x).strip() != 'nan' else 'U')
                    df_owner['Owner Label'] = df_owner['Lead Owner'] + " (" + df_owner['Owner Display'] + ")"
                    
                    owner_status = df_owner.groupby(['Owner Label', 'Status']).size().reset_index(name='Count')
                    
                    fig_o = px.bar(owner_status, x='Count', y='Owner Label', color='Status', orientation='h', 
                                   color_discrete_map=p_colors, barmode='stack', title=f"{title_prefix} Status by Owner")
                    
                    fig_o.update_layout(
                        xaxis_type='log', # LOG SCALE to handle Unassigned
                        height=450, showlegend=True,
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        margin=dict(l=20, r=20, t=20, b=20),
                        font=dict(family="Inter, sans-serif")
                    )
                    fig_o.update_traces(marker_line_width=0, opacity=0.9)
                    st.plotly_chart(fig_o, use_container_width=True)
            
            with col_chart2:
                if 'Status' in df_f.columns:
                    status_counts = df_f.groupby('Status').size().reset_index(name='Count').sort_values('Count', ascending=False)
                    total_status = status_counts['Count'].sum()
                    
                    fig_s = px.pie(status_counts, values='Count', names='Status', hole=0.6,
                                   color='Status', color_discrete_map=p_colors, title=f"{title_prefix} Opportunity Status Distribution")
                    
                    fig_s.update_traces(textposition='outside', textinfo='percent+label', marker=dict(line=dict(color='white', width=2)))
                    # CENTER TEXT
                    fig_s.add_annotation(text=f"<b>{total_status:,}</b><br>Total", showarrow=False, font_size=20, font_family="Inter, sans-serif")
                    
                    fig_s.update_layout(height=450, showlegend=False, paper_bgcolor='rgba(0,0,0,0)', font=dict(family="Inter, sans-serif", color=text_color))
                    st.plotly_chart(fig_s, use_container_width=True)
            
            st.divider()
            
            # 3. Phase-Based Pipeline Funnel
            st.markdown(f"### {title_prefix} **3. Phase-Based Pipeline Funnel (L2C Education)**")
            if 'Pipeline' in df_f.columns and 'Status' in df_f.columns:
                l2c_df = df_f[df_f['Pipeline'] == 'L2C - Education'].copy()
                if not l2c_df.empty:
                    funnel_data = []
                    if 'Stage' in l2c_df.columns:
                        for stage in STAGE_ORDER[:-1]:
                            stage_df = l2c_df[(l2c_df['Stage'] == stage) & (l2c_df['Status'] == 'open')]
                            funnel_data.append({'Stage': stage, 'Count': len(stage_df)})
                        won_df = l2c_df[l2c_df['Status'] == 'won']
                        funnel_data.append({'Stage': 'Won', 'Count': len(won_df)})
                    
                    if funnel_data:
                        f_df = pd.DataFrame(funnel_data)
                        f_df['Prev Count'] = f_df['Count'].shift(1)
                        f_df['Conv Rate'] = (f_df['Count'] / f_df['Prev Count'] * 100).fillna(0)
                        
                        fig_f = go.Figure()
                        fig_f.add_trace(go.Bar(
                            y=f_df['Stage'], x=f_df['Count'], orientation='h',
                            marker=dict(
                                color=f_df['Count'],
                                colorscale=[[0, '#cffafe'], [0.5, '#3b82f6'], [1, '#10b981']],
                                line=dict(width=0)
                            ),
                            text=f_df['Count'], textposition='outside',
                            hovertemplate='<b>%{y}</b><br>Count: %{x}<extra></extra>'
                        ))
                        
                        for i in range(1, len(f_df)):
                            rate = f_df.iloc[i]['Conv Rate']
                            if rate > 0:
                                fig_f.add_annotation(
                                    x=f_df.iloc[i]['Count'] / 2, y=i - 0.5,
                                    text=f"<b>{rate:.1f}%</b>", showarrow=False,
                                    font=dict(size=10, color="white"),
                                    bgcolor="#6366f1", borderpad=4, opacity=0.8
                                )
                        
                        fig_f.update_layout(
                            height=500, showlegend=False,
                            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            margin=dict(l=20, r=40, t=20, b=20),
                            yaxis=dict(autorange="reversed", showgrid=False),
                            title=f"{title_prefix} Pipeline Velocity"
                        )
                        st.plotly_chart(fig_f, use_container_width=True)

            st.divider()
            
            # 4. Lead Source Analysis
            st.markdown(f"### {title_prefix} **4. Lead Source Analysis**")
            if 'Lead Source' in df_f.columns and 'Status' in df_f.columns:
                lead_counts = df_f.groupby('Lead Source').size().reset_index(name='Total').sort_values('Total', ascending=False)
                top_12 = lead_counts.head(12)['Lead Source'].tolist()
                
                df_lead = df_f.copy()
                df_lead['Lead Category'] = df_lead['Lead Source'].apply(lambda x: x if x in top_12 else 'Others')
                lead_status = df_lead.groupby(['Lead Category', 'Status']).size().reset_index(name='Count')
                
                fig_l = px.bar(lead_status, x='Count', y='Lead Category', color='Status', orientation='h',
                               color_discrete_map=p_colors, barmode='stack', title=f"{title_prefix} Conversion by Source")
                
                fig_l.update_layout(
                    height=500, showlegend=True,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=20, r=20, t=10, b=10),
                    font=dict(family="Inter, sans-serif"),
                    xaxis=dict(showgrid=True, gridcolor=border_color)
                )
                fig_l.update_traces(marker_line_width=0, opacity=0.9)
                st.plotly_chart(fig_l, use_container_width=True)

            st.divider()
            # 5. Opportunity Pipeline Bubble Chart
            st.markdown(f"### {title_prefix} **5. Opportunity Pipeline Bubble Chart**")
            if 'Status' in df_f.columns and 'Stage Percentage' in df_f.columns:
                open_opps = df_f[df_f['Status'] == 'open'].copy()
                if not open_opps.empty and 'Lead Source' in open_opps.columns:
                    bubble_data = open_opps.groupby('Lead Source').agg({'Opportunity Name': 'count', 'Opportunity Value': 'sum', 'Stage Percentage': 'mean'}).reset_index()
                    bubble_data.columns = ['Lead Source', 'Count', 'Value', 'Avg Stage %']
                    if not bubble_data.empty:
                        fig_b = px.scatter(bubble_data, x='Avg Stage %', y='Value', size='Count', color='Lead Source', 
                                         title=f"{title_prefix} Lead Source Performance (Open Context)",
                                         color_discrete_sequence=['#1e3a8a', '#10b981', '#3b82f6', '#94a3b8', '#6366f1'],
                                         size_max=45)
                        
                        fig_b.update_layout(
                            height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(family="Inter, sans-serif", color=text_color),
                            xaxis=dict(title="Stage Progress (%)", tickformat='.0f', gridcolor=border_color),
                            yaxis=dict(title="Pipeline Value ($)", gridcolor=border_color)
                        )
                        fig_b.update_traces(marker=dict(line=dict(width=1, color='white'), opacity=0.8))
                        st.plotly_chart(fig_b, use_container_width=True)
                        st.caption("Visual hierarchy: Bubble size = Opp Count | Color = Source | X = Progress")
        
        if pipe_comparison_mode and len(sel_pipe_countries) == 2:
            pc1, pc2 = sel_pipe_countries[0], sel_pipe_countries[1]
            st.markdown(f"## ⚔️ Comparison: {pc1} vs {pc2}")
            p_comp_col1, p_comp_col2 = st.columns(2)
            with p_comp_col1: render_pipeline_content(opps[opps['Country']==pc1], f"💼 {pc1}")
            with p_comp_col2: render_pipeline_content(opps[opps['Country']==pc2], f"💼 {pc2}")
        else:
            render_pipeline_content(opps_filtered)

    else:
        st.info("No opportunity data found.")
# Sidebar toggle for width
width_option = st.sidebar.radio("View Mode", ["Narrow", "Wide"])

# Set layout based on selection
if width_option == "Wide":
    layout_mode = "wide"
else:
    layout_mode = "centered"

st.set_page_config(layout=layout_mode)
# --- TAB 5: ATTRIBUTION ANALYSIS ---
with tabs[5]:
    if not contacts.empty:
        # Define geo filter function helper
        def apply_contact_geo_filter(df_to_filt):
            c_geo_col1, c_geo_col2 = st.columns([3, 1])
            with c_geo_col1:
                # Removed City filter for consistency with GA4/GSC requirements
                if 'country' in df_to_filt.columns:
                    geo_options = [str(x) for x in df_to_filt['country'].dropna().unique() if str(x).strip()]
                    selected_geo = st.multiselect("Filter Attribution by Country", ["All"] + sorted(geo_options), default="All", key="c_country_val")
                    if "All" not in selected_geo and selected_geo:
                        return df_to_filt[df_to_filt['country'].isin(selected_geo)]
            return df_to_filt

        contacts_filtered = apply_contact_geo_filter(contacts)
        st.markdown(f"<small>Records: {len(contacts_filtered)} contacts</small>", unsafe_allow_html=True)
        st.markdown("---")

        st.markdown("### **1. Attribution Analysis (First vs. Latest)**")
        if 'first_attribution' in contacts_filtered.columns and 'latest_attribution' in contacts_filtered.columns:
            # Aggregate First vs latest
            f_counts = contacts_filtered['first_attribution'].value_counts().reset_index().head(15)
            f_counts.columns = ['Source', 'First']
            l_counts = contacts_filtered['latest_attribution'].value_counts().reset_index().head(15)
            l_counts.columns = ['Source', 'Latest']
            attr_df = pd.merge(f_counts, l_counts, on='Source', how='outer').fillna(0)
            
            fig_attr = go.Figure()
            fig_attr.add_trace(go.Bar(y=attr_df['Source'], x=attr_df['First'], name='First Attrib', orientation='h', marker=dict(color='#0ea5e9')))
            fig_attr.add_trace(go.Bar(y=attr_df['Source'], x=attr_df['Latest'], name='Latest Attrib', orientation='h', marker=dict(color='#10b981')))
            fig_attr.update_layout(barmode='stack', title="Attribution Source Transition", yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(apply_chart_style(fig_attr), use_container_width=True)
            
            st.markdown("#### **Attribution Detail Table**")
            st.dataframe(style_df(attr_df), use_container_width=True, hide_index=True)

            st.markdown("#### **First Attribution Distribution**")
            fig_pie = px.pie(attr_df, values='First', names='Source', hole=0.5, title="First Attribution Breakdown")
            st.plotly_chart(apply_chart_style(fig_pie), use_container_width=True)
        
        st.divider()
        st.markdown("### **2. Lead Source Summary**")
        if 'source' in contacts_filtered.columns:
            ls_sum = contacts_filtered['source'].value_counts().reset_index().head(20)
            st.dataframe(style_df(ls_sum), use_container_width=True, hide_index=True)
    else:
        st.info("No contact data found.")

# --- TAB 6: CONSULTANT CAPACITY ---
with tabs[6]:
    st.markdown("### **👨‍🏫 Consultant Pulse Leaderboard**")
    
    # KPI Summary for Capacities
    df_t = pd.DataFrame(consultant_today)
    df_w = pd.DataFrame(consultant_weekly)
    
    t_appts = int(df_t['total_appointments'].sum()) if not df_t.empty else 0
    w_appts = int(df_w['total_appointments'].sum()) if not df_w.empty else 0
    
    st.markdown(f"""
    <div style='display: flex; justify-content: center; gap: 20px; margin-bottom: 2rem;'>
        <div style='padding: 20px 40px; background: rgba(16,185,129,0.1); border: 1px solid #10b981; border-radius: 12px; box-shadow: 0 0 20px rgba(16,185,129,0.2); text-align: center;'>
            <span style='color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.1em;'>Today's Total Workforce</span>
            <h2 style='color: #10b981; margin: 10px 0 0; font-size: 2.2rem;'>{t_appts} Appts</h2>
        </div>
        <div style='padding: 20px 40px; background: rgba(139,92,252,0.1); border: 1px solid #8b5cfc; border-radius: 12px; box-shadow: 0 0 20px rgba(139,92,252,0.2); text-align: center;'>
            <span style='color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.1em;'>Weekly Total Workforce (7D)</span>
            <h2 style='color: #8b5cfc; margin: 10px 0 0; font-size: 2.2rem;'>{w_appts} Appts</h2>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # --- TODAY'S SECTION ---
    st.markdown("### **📅 Today's Consultant Capacity**")
    if not df_t.empty:
        fig_t = px.bar(df_t.sort_values('total_appointments'), x="total_appointments", y="consultant_name", 
                        orientation='h', title="Appointments per Consultant (Today)", color="total_appointments", color_continuous_scale="Blues", labels={'consultant_name': 'Consultant', 'total_appointments': 'Appointments'})
        st.plotly_chart(apply_chart_style(fig_t), use_container_width=True)
        
        st.markdown("#### **Today's Leaderboard**")
        cols = ['consultant_name', 'total_appointments', 'amount_paid', 'confirmed', 'show', 'no_show', 'unconfirmed', 'country']
        available_cols = [c for c in cols if c in df_t.columns]
        df_t_disp = df_t[available_cols].sort_values('total_appointments', ascending=False)
        st.dataframe(style_df(df_t_disp), use_container_width=True, hide_index=True)
    else:
        st.info("No appointment data for today.")
    
    st.divider()
    
    # --- WEEKLY SECTION ---
    st.markdown("### **📆 Weekly Consultant Capacity (Last 7 Rolling Days)**")
    
    if not df_w.empty:
        fig_w = px.bar(df_w.sort_values('total_appointments'), x="total_appointments", y="consultant_name", 
                        orientation='h', title="Appointments per Consultant (Weekly Rolling 7D)", color="total_appointments", color_continuous_scale="Greens", labels={'consultant_name': 'Consultant', 'total_appointments': 'Appointments'})
        st.plotly_chart(apply_chart_style(fig_w), use_container_width=True)
        
        st.markdown("#### **Weekly Leaderboard (Rolling 7D)**")
        cols_w = ['consultant_name', 'total_appointments', 'amount_paid', 'confirmed', 'show', 'no_show', 'unconfirmed', 'country']
        available_cols_w = [c for c in cols_w if c in df_w.columns]
        df_w_disp = df_w[available_cols_w].sort_values('total_appointments', ascending=False)
        st.dataframe(style_df(df_w_disp), use_container_width=True, hide_index=True)
    else:
        st.info("No appointment data for this week.")

