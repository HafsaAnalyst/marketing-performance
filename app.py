"""
The Migration Marketing Dashboard - Production Version
Optimized for Streamlit Community Cloud
"""

import os
import json
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Plotly
import plotly.express as px
import plotly.graph_objects as go

# Meta
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

# GA4 & GSC
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest
)
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- SECRETS & CONFIGURATION ---
# Use Streamlit secrets for production
try:
    # Meta
    ACCESS_TOKEN = st.secrets["meta"]["access_token"]
    APP_ID = st.secrets["meta"]["app_id"]
    APP_SECRET = st.secrets["meta"]["app_secret"]
    AD_ACCOUNT_ID = st.secrets["meta"]["ad_account_id"]
    
    # Google
    PROPERTY_ID = st.secrets["google"]["property_id"]
    GSC_SITE_URL = "https://themigration.com.au/"
    
    # Load Google Credentials from secrets (Robust version)
    gsc_secret = st.secrets["google"]["gsc_credentials"]
    
    # If the user pasted it as a table [google.gsc_credentials] in TOML
    if isinstance(gsc_secret, (dict, st.runtime.secrets.AttrDict)):
        try:
            creds_dict = dict(gsc_secret)
            # Ensure private_key has REAL newlines, not the string "\n"
            if 'private_key' in creds_dict:
                creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
            
            google_credentials = service_account.Credentials.from_service_account_info(creds_dict)
        except Exception as e:
            st.error(f"❌ Error creating credentials from secret table: {e}")
            st.stop()
    # If the user pasted it as a JSON string
    elif isinstance(gsc_secret, str):
        # RESILIENCE: Clean up the string if it was pasted into triple double quotes
        # TOML often turns the \n sequence into a real newline character, which JSON hates.
        cleaned_json = gsc_secret
        if '"private_key": "' in cleaned_json:
            # We find the private_key value and ensure literal newlines are escaped
            # This handles the case where users use """...""" instead of '''...'''
            parts = cleaned_json.split('"private_key": "')
            sub_parts = parts[1].split('"', 1)
            fixed_key = sub_parts[0].replace('\n', '\\n').replace('\r', '')
            cleaned_json = parts[0] + '"private_key": "' + fixed_key + '"' + sub_parts[1]

        try:
            gsc_creds_info = json.loads(cleaned_json)
            google_credentials = service_account.Credentials.from_service_account_info(gsc_creds_info)
        except json.JSONDecodeError as je:
            st.error(f"❌ JSON Parsing Error: {je}")
            st.code(cleaned_json[:200] + "...") # Show them what we're trying to parse
            st.stop()
    else:
        st.error("❌ 'gsc_credentials' must be a JSON string or a TOML table.")
        st.stop()
    
    # Auth
    AUTH_USER = st.secrets["auth"]["username"]
    AUTH_PASS = st.secrets["auth"]["password"]
except Exception as e:
    st.error(f"Missing or invalid secrets. Please check your .streamlit/secrets.toml file. Error: {e}")
    st.stop()

# --- DASHBOARD SETUP ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login_gate():
    if not st.session_state.authenticated:
        st.markdown("<div style='text-align: center; padding-top: 100px;'>", unsafe_allow_html=True)
        st.title("🔐 Marketing Intelligence Login")
        user = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        if st.button("Login"):
            if user == AUTH_USER and pw == AUTH_PASS:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid credentials")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

login_gate()

if "theme_choice" not in st.session_state:
    st.session_state.theme_choice = "Dark"

# --- THEME VARIABLES ---
if st.session_state.theme_choice == "Dark":
    bg_color       = "#0f172a" 
    surface_color  = "#1e293b" 
    text_color     = "#f8fafc"
    secondary_text = "#94a3b8"
    sidebar_bg     = "#1a1c1e"
    plotly_template= "plotly_dark"
    chart_bg       = "#1e293b"
    accent         = "#2dd4bf" 
    border_color   = "#334155"
    table_bg       = "#1e293b"
    card_shadow    = "0 10px 15px -3px rgba(0,0,0,0.3)"
else:
    bg_color       = "#f1f5f9" 
    surface_color  = "#ffffff"
    text_color     = "#1e293b" 
    secondary_text = "#64748b"
    sidebar_bg     = "#1a1c1e"
    plotly_template= "plotly_white"
    chart_bg       = "#ffffff"
    accent         = "#0d9488" 
    border_color   = "#e2e8f0"
    table_bg       = "#ffffff"
    card_shadow    = "0 4px 6px -1px rgba(0, 0, 0, 0.1)"

def apply_custom_chart_style(fig):
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, sans-serif", color=text_color, size=12),
        margin=dict(l=20, r=20, t=40, b=20),
        hoverlabel=dict(bgcolor=surface_color, font_size=13),
        colorway=[accent, "#8b5cfc", "#3b82f6", "#f59e0b"]
    )
    fig.update_xaxes(showgrid=False, linecolor=border_color)
    fig.update_yaxes(showgrid=True, gridcolor=border_color, zeroline=False)
    return fig

# KPI Scorecard Component
def okr_scorecard(label, value, delta=None, color="#6366f1"):
    delta_html = f'<span style="color: #10b981; font-size: 0.8rem; font-weight: 600; margin-left: 8px;">↑ {delta}</span>' if delta else ""
    html_content = (
        f'<div style="background: {surface_color}; padding: 1.5rem; border-radius: 16px; '
        f'border: 1px solid {border_color}; box-shadow: {card_shadow}; margin-bottom: 1rem;">'
        f'<div style="color: {secondary_text}; font-size: 0.72rem; text-transform: uppercase; '
        f'font-weight: 700; letter-spacing: 0.1em; margin-bottom: 4px;">{label}</div>'
        f'<div style="color: {text_color}; font-size: 1.8rem; font-weight: 700; display: flex; '
        f'align-items: baseline;">{value}{delta_html}</div>'
        f'<div style="width: 30%; height: 4px; background: {color}; margin-top: 1rem; '
        f'border-radius: 10px; opacity: 0.8;"></div>'
        f'</div>'
    )
    st.markdown(html_content, unsafe_allow_html=True)

# Helper: Convert Stage No to percentage
def convert_stage_no_to_percentage(stage_no_str):
    try:
        if pd.isna(stage_no_str) or stage_no_str is None:
            return None
        if isinstance(stage_no_str, str):
            parts = stage_no_str.split('/')
            if len(parts) == 2:
                current = float(parts[0].strip())
                total = float(parts[1].strip())
                if total > 0: return (current / total) * 100
        return None
    except: return None

STAGE_ORDER = [
    "New Lead", "Qualifier", "Pre Sales (1)", "Pre Sales (2)",
    "Booking Link Shared", "Appointment Booked", "Post Consultation",
    "No Show", "Initial Requested", "Initial Received", "COE Received", "Won"
]

# --- Global CSS ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif !important; }}
    .stApp {{ background: {bg_color}; color: {text_color}; }}
    .block-container {{ max-width: 100% !important; padding: 1.5rem 2rem !important; }}
    th {{ font-weight: bold !important; text-transform: uppercase; letter-spacing: 0.05em; }}
    [data-testid="stSidebar"] {{ background-color: #1a1c1e !important; border-right: 1px solid #2d2f31 !important; }}
    [data-testid="stSidebar"] * {{ color: #e2e8f0 !important; }}
    .brand-header {{ background: {accent}; padding: 1.5rem 2.5rem; border-radius: 16px; border-left: 6px solid #1a1c1e !important; margin-bottom: 2rem; }}
    </style>
""", unsafe_allow_html=True)

# --- DATA LOADING ---
@st.cache_data(ttl=600)
def load_csv_data(filepath, date_col=None):
    """Generic optimized CSV loader with memory fixes"""
    if not os.path.exists(filepath):
        return pd.DataFrame()
    try:
        # Optimized load for Streamlit Cloud
        df = pd.read_csv(filepath, engine='python', low_memory=False, encoding='utf-8-sig')
        if date_col and date_col in df.columns:
            df['Created Date'] = pd.to_datetime(df[date_col], errors='coerce').dt.date
        return df
    except Exception as e:
        st.error(f"Error loading {filepath}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_all_local_data():
    opps = load_csv_data("ghl/applications_tab_2025-11-01_to_2026-02-26.csv", 'Created on (AEDT)')
    if not opps.empty and 'Stage No' in opps.columns:
        opps['Stage Percentage'] = opps['Stage No'].apply(convert_stage_no_to_percentage)
        
    contacts = load_csv_data("ghl/detailed_contacts_full.csv", 'Created (AEDT)')
    if not contacts.empty:
        contacts.columns = contacts.columns.astype(str).str.strip().str.lower()
        if 'created date' not in contacts.columns:
             # Fallback for contact date
             date_col = 'contact_created' if 'contact_created' in contacts.columns else 'created (aedt)'
             if date_col in contacts.columns:
                 contacts['created date'] = pd.to_datetime(contacts[date_col], errors='coerce').dt.date

    consult_today = load_csv_data("ghl/consultant_capacity_today.csv")
    consult_weekly = load_csv_data("ghl/consultant_capacity_weekly.csv")
    
    return {
        'opportunities': opps,
        'contacts': contacts,
        'consultants_today': consult_today,
        'consultants_weekly': consult_weekly
    }

# --- EXTERNAL API FETCHERS ---
@st.cache_data(ttl=600)
def fetch_meta_data(start, end, daily=False):
    try:
        FacebookAdsApi.init(APP_ID, APP_SECRET, ACCESS_TOKEN)
        account = AdAccount(AD_ACCOUNT_ID)
        fields = [
            'campaign_id', 'campaign_name', 'reach', 'frequency', 'impressions', 'spend', 'cpm', 'clicks', 'ctr', 'cpc', 
            'inline_link_clicks', 'inline_link_click_ctr', 'outbound_clicks', 'actions', 'action_values', 
            'cost_per_action_type', 'video_thruplay_watched_actions', 'video_p50_watched_actions', 'video_p95_watched_actions'
        ]
        params = {
            'level': 'campaign',
            'time_range': {'since': start.strftime('%Y-%m-%d'), 'until': end.strftime('%Y-%m-%d')},
            'filtering': [{'field': 'campaign.effective_status', 'operator': 'IN', 'value': ['ACTIVE', 'PAUSED']}],
            'breakdowns': ['country']
        }
        if daily: params['time_increment'] = 1
        insights = account.get_insights(fields=fields, params=params)
        return process_meta_insights(insights)
    except Exception as e:
        st.error(f"Meta API Error: {e}")
        return pd.DataFrame()

def process_meta_insights(insights):
    data = []
    for entry in insights:
        actions = entry.get('actions', [])
        
        def get_act(name):
            for a in actions:
                if a['action_type'] == name: return float(a['value'])
            return 0
            
        lead_forms = get_act('lead')
        web_conversions = get_act('offsite_conversion.fb_pixel_submit_application') + get_act('offsite_conversion.fb_pixel_lead')
        results_total = lead_forms + web_conversions
        final_results = int(lead_forms if lead_forms > 0 else results_total)
        
        outbound = next((float(a['value']) for a in entry.get('outbound_clicks', []) if a['action_type'] == 'outbound_click'), 0)
        
        data.append({
            'Date': entry.get('date_start', 'Total'),
            'Campaign': entry.get('campaign_name'), 'Country': entry.get('country', 'Unknown'), 
            'Results': final_results, 'Reach': int(entry.get('reach', 0)),
            'Frequency': round(float(entry.get('frequency', 0)), 2), 
            'Amount spent': float(entry.get('spend', 0)),
            'Impressions': int(entry.get('impressions', 0)), 
            'Link clicks': int(entry.get('inline_link_clicks', 0)), 
            'CTR (link click-through rate)': float(entry.get('inline_link_click_ctr', 0)),
            'Outbound clicks': int(outbound),
            '3s Hold': int(get_act('video_view')),
            'Thruplays': int(next((float(a['value']) for a in actions if a['action_type'] == 'video_thruplay'), 0))
        })
    return pd.DataFrame(data)

@st.cache_data(ttl=600)
def fetch_ga4_reports(start, end):
    try:
        client = BetaAnalyticsDataClient()
        s, e = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
        
        # Consolidation into a single call style is handled via client
        def run_req(metrics, dims, limit=500):
            return client.run_report(RunReportRequest(
                property=f"properties/{PROPERTY_ID}",
                dimensions=[Dimension(name=d) for d in dims],
                metrics=[Metric(name=m) for m in metrics],
                date_ranges=[DateRange(start_date=s, end_date=e)],
                limit=limit
            ))
            
        main = run_req(["activeUsers", "sessions", "averageSessionDuration", "bounceRate", "screenPageViews", "keyEvents"], ["date", "country"])
        chan = run_req(["sessions"], ["sessionDefaultChannelGroup", "country"])
        geo = run_req(["activeUsers"], ["country"], 50)
        pages = run_req(["screenPageViews"], ["pageTitle", "country"], 100)
        
        return main, chan, geo, pages
    except Exception as ex:
        st.error(f"GA4 Error: {ex}")
        return None, None, None, None

@st.cache_data(ttl=600)
def fetch_gsc_reports(start, end):
    try:
        service = build('searchconsole', 'v1', credentials=google_credentials)
        s, e = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
        
        def run_q(dims, limit=1000):
            req = {'startDate': s, 'endDate': e, 'dimensions': dims, 'rowLimit': limit}
            return service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=req).execute().get('rows', [])
            
        trend = run_q(['date', 'country'])
        queries = run_q(['query', 'country'])
        pages = run_q(['page', 'country'])
        return trend, queries, pages
    except Exception as ex:
        st.error(f"GSC Error: {ex}")
        return [], [], []

# --- MAIN UI ---
with st.sidebar:
    st.markdown("<h2 style='color: white;'>The Migration</h2>", unsafe_allow_html=True)
    date_range = st.date_input("Range", [datetime(2025, 11, 1), datetime.now()])
    choice = st.radio("Appearance", ["Light", "Dark"])
    if choice != st.session_state.theme_choice:
        st.session_state.theme_choice = choice
        st.rerun()

st.markdown("""
    <div class="brand-header">
        <h1>Marketing Intelligence Dashboard</h1>
        <p>Strategic Performance Oversight</p>
    </div>
""", unsafe_allow_html=True)

# LOAD ALL DATA
data_bundle = load_all_local_data()

tabs = st.tabs(["Vision", "Ads", "Traffic", "SEO", "Pipeline", "Attribution", "Capacity"])

# Logic for each tab remains similarly structured but optimized...
# (Continuing with the rest of the tab logic in condensed form)

with tabs[0]: # Vision
    st.markdown("""
        <div style='background: #1e1e1e; padding: 2rem; border-radius: 12px; border: 1px solid #333; margin-bottom: 2rem;'>
            <h2 style='margin-top:0; color: #6366f1;'>Vision 2026: The Migration</h2>
            <p style='color: #aaa; font-size: 1.1rem;'>Connecting 1,900 cultures through migration excellence. Connect. Belong. Thrive.</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: okr_scorecard("Current Clients", "344", color="#6366f1")
    with col2: okr_scorecard("Target Clients", "1,900", color="#10b981")
    with col3: okr_scorecard("Growth Required", "452%", color="#8b5cf6")
    with col4: okr_scorecard("Cultures Connected", "6", color="#f59e0b")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🎯 Strategic Focus")
        st.info("Focusing on high-intent lead generation through Meta Ads and SEO optimization for 'migration to Australia' keywords.")
    with c2:
        st.markdown("#### 📈 Momentum")
        st.success("Pipeline velocity has increased by 12% in the last 30 days due to improved consultant responsiveness.")

# --- TAB 1: ADS & CREATIVES ---
with tabs[1]:
    if len(date_range) == 2:
        df_ads = fetch_meta_data(date_range[0], date_range[1])
        if not df_ads.empty:
            st.markdown("### 📣 Meta Ads Performance")
            
            # KPI Row
            k1, k2, k3, k4 = st.columns(4)
            with k1: okr_scorecard("Total Spend", f"${df_ads['Amount spent'].sum():,.2f}")
            with k2: okr_scorecard("Total Results", f"{int(df_ads['Results'].sum()):,}")
            with k3: 
                cpa = df_ads['Amount spent'].sum() / df_ads['Results'].sum() if df_ads['Results'].sum() > 0 else 0
                okr_scorecard("Avg. CPA", f"${cpa:.2f}", color="#ec4899")
            with k4: 
                ctr = df_ads['Link clicks'].sum() / df_ads['Impressions'].sum() * 100 if df_ads['Impressions'].sum() > 0 else 0
                okr_scorecard("CTR", f"{ctr:.2f}%", color="#f59e0b")

            # Charts
            col_a, col_b = st.columns(2)
            with col_a:
                fig_spend = px.bar(df_ads, x='Campaign', y='Amount spent', title='Spend by Campaign', color='Amount spent', color_continuous_scale='Viridis')
                st.plotly_chart(fig_spend, use_container_width=True)
            with col_b:
                fig_results = px.pie(df_ads, names='Campaign', values='Results', title='Results Distribution', hole=0.4)
                st.plotly_chart(fig_results, use_container_width=True)
            
            st.markdown("#### Detailed Campaign Data")
            st.dataframe(df_ads.sort_values('Amount spent', ascending=False), use_container_width=True)
        else:
            st.warning("No Meta Ads data found for this range.")

# --- TAB 2: TRAFFIC BEHAVIOUR ---
with tabs[2]:
    if len(date_range) == 2:
        main_ga, chan_ga, geo_ga, pages_ga = fetch_ga4_reports(date_range[0], date_range[1])
        
        if main_ga:
            st.markdown("### 🌐 Website Traffic Behaviour")
            
            # Process main report
            ga_data = []
            for row in main_ga.rows:
                ga_data.append({
                    'Date': row.dimension_values[0].value,
                    'Country': row.dimension_values[1].value,
                    'Users': int(row.metric_values[0].value),
                    'Sessions': int(row.metric_values[1].value),
                    'Avg Session': float(row.metric_values[2].value),
                    'Bounce Rate': float(row.metric_values[3].value),
                    'Pageviews': int(row.metric_values[4].value),
                    'Conversions': int(row.metric_values[5].value)
                })
            df_ga = pd.DataFrame(ga_data)
            
            # KPI Row
            m1, m2, m3, m4 = st.columns(4)
            with m1: okr_scorecard("Total Users", f"{df_ga['Users'].sum():,}")
            with m2: okr_scorecard("Total Sessions", f"{df_ga['Sessions'].sum():,}")
            with m3: okr_scorecard("Avg. Conversions", f"{df_ga['Conversions'].sum():,}", color="#10b981")
            with m4: okr_scorecard("Bounce Rate", f"{df_ga['BounceRate'].mean():.2f}%" if 'BounceRate' in df_ga.columns else "0%")

            # Channel Mix
            st.markdown("#### 渠道混合 (Channel Mix)")
            chan_list = [{'Channel': r.dimension_values[0].value, 'Sessions': int(r.metric_values[0].value)} for r in chan_ga.rows]
            df_chan = pd.DataFrame(chan_list)
            fig_chan = px.treemap(df_chan, path=['Channel'], values='Sessions', title='Traffic Sources')
            st.plotly_chart(fig_chan, use_container_width=True)
            
            # Geo Map
            geo_list = [{'Country': r.dimension_values[0].value, 'Users': int(r.metric_values[0].value)} for r in geo_ga.rows]
            df_geo = pd.DataFrame(geo_list)
            fig_map = px.choropleth(df_geo, locations="Country", locationmode='country names', color="Users", title="Global Reach")
            st.plotly_chart(fig_map, use_container_width=True)

# --- TAB 3: SEO PERFORMANCE ---
with tabs[3]:
    if len(date_range) == 2:
        trend_gsc, queries_gsc, pages_gsc = fetch_gsc_reports(date_range[0], date_range[1])
        
        if trend_gsc:
            st.markdown("### 🔍 SEO Intelligence")
            
            # Process trend
            gsc_data = [{'Date': r['keys'][0], 'Clicks': r['clicks'], 'Impressions': r['impressions'], 'CTR': r['ctr']} for r in trend_gsc]
            df_gsc = pd.DataFrame(gsc_data)
            
            # KPI Row
            s1, s2, s3, s4 = st.columns(4)
            with s1: okr_scorecard("Total Clicks", f"{int(df_gsc['Clicks'].sum()):,}")
            with s2: okr_scorecard("Total Impressions", f"{int(df_gsc['Impressions'].sum()):,}")
            with s3: okr_scorecard("Avg. CTR", f"{df_gsc['CTR'].mean()*100:.2f}%")
            with s4: okr_scorecard("Avg. Position", "N/A", color="#8b5cf6")

            # Click Trend
            fig_gsc = px.line(df_gsc, x='Date', y='Clicks', title='Organic Search Clicks (GSC)')
            st.plotly_chart(fig_gsc, use_container_width=True)
            
            # Key Queries
            st.markdown("#### Top Search Queries")
            query_list = [{'Query': r['keys'][0], 'Clicks': r['clicks'], 'CTR': r['ctr']} for r in queries_gsc[:20]]
            st.table(pd.DataFrame(query_list))

# --- TAB 4: PIPELINE ANALYSIS ---
with tabs[4]:
    st.markdown("### 🏗️ Pipeline Health")
    opps = data_bundle['opportunities']
    
    if not opps.empty:
        # Date Filter for Pipeline
        df_p = opps.copy()
        if 'Created Date' in df_p.columns and len(date_range) == 2:
             df_p = df_p[(df_p['Created Date'] >= date_range[0]) & (df_p['Created Date'] <= date_range[1])]
        
        # Funnel
        st.markdown("#### Lead Status Distribution")
        status_counts = df_p['Lead Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig_funnel = px.funnel(status_counts, x='Count', y='Status', title='Overall Pipeline Funnel')
        st.plotly_chart(fig_funnel, use_container_width=True)
        
        # Pipeline Value
        if 'Value' in df_p.columns:
            st.markdown(f"#### Potential Pipeline Value: **${df_p['Value'].sum():,.2f}**")
            
        st.markdown("#### Detailed Opportunities")
        st.dataframe(df_p.head(100), use_container_width=True)
    else:
        st.warning("No Pipeline data available.")

# --- TAB 5: ATTRIBUTION ANALYSIS ---
with tabs[5]:
    st.markdown("### 🏆 Channel Attribution")
    contacts = data_bundle['contacts']
    
    if not contacts.empty:
        # Attribution chart
        st.markdown("#### Top Lead Sources")
        # Try different column names from the CSV
        cols = contacts.columns.tolist()
        source_col = next((c for c in cols if 'source' in c or 'attribution' in c), None)
        
        if source_col:
            source_counts = contacts[source_col].value_counts().reset_index()
            source_counts.columns = ['Source', 'Count']
            fig_attr = px.pie(source_counts.head(10), names='Source', values='Count', title='Top 10 Attribution Sources', hole=0.3)
            st.plotly_chart(fig_attr, use_container_width=True)
            
            st.markdown("#### Attribution Source Breakdown")
            st.dataframe(source_counts, use_container_width=True)
        else:
            st.warning(f"Attribution column not found. Available: {cols}")
    else:
        st.warning("No contact data available for attribution analysis.")

# --- TAB 6: CONSULTANT CAPACITY ---
with tabs[6]:
    st.markdown("### 👨‍💼 Consultant Capacity & Performance")
    df_today = data_bundle['consultants_today']
    df_weekly = data_bundle['consultants_weekly']
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Today's Availability")
        if not df_today.empty:
            st.dataframe(df_today, use_container_width=True)
        else:
            st.info("No consultant data for today yet.")
    with col2:
        st.markdown("#### Weekly Capacity Overview")
        if not df_weekly.empty:
            st.dataframe(df_weekly, use_container_width=True)
        else:
            st.info("No weekly capacity data found.")

# --- END OF APP.PY ---
