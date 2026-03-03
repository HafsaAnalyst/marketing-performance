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
# --- UPDATED THEME VARIABLES (Complete) ---
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
    table_bg       = "#1e293b"  # <-- Added missing variable
    btn_bg         = "#ffffff"
    btn_text       = "#000000"
    input_bg       = "#2d2f31"
    input_text     = "#ffffff"
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
    table_bg       = "#ffffff"  # <-- Added missing variable
    btn_bg         = "#1a1c1e"
    btn_text       = "#ffffff"
    input_bg       = "#f8fafc"
    input_text     = "#1e293b"
    card_shadow    = "0 4px 6px -1px rgba(0, 0, 0, 0.1)"

# --- Global CSS for Bold Table Headings ---
st.markdown("""
<style>
    th { font-weight: bold !important; text-transform: uppercase; letter-spacing: 0.05em; }
</style>
""", unsafe_allow_html=True)

def okr_scorecard(label, value, delta=None, color="#6366f1"):
    """
    Fixed KPI card function. 
    This version uses a joined string to prevent the '</div>' rendering error.
    """
    # Create delta logic
    delta_html = f'<span style="color: #10b981; font-size: 0.8rem; font-weight: 600; margin-left: 8px;">↑ {delta}</span>' if delta else ""
    
    # We build the HTML as a single clean string to avoid indentation issues
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

def convert_stage_no_to_percentage(stage_no_str):
    """Convert Stage No (e.g., '1 / 11') to percentage"""
    try:
        if pd.isna(stage_no_str) or stage_no_str is None:
            return None
        if isinstance(stage_no_str, str):
            parts = stage_no_str.split('/')
            if len(parts) == 2:
                current = float(parts[0].strip())
                total = float(parts[1].strip())
                if total > 0:
                    return (current / total) * 100
        return None
    except:
        return None

# L2C Education Stage Order
STAGE_ORDER = [
    "New Lead", "Qualifier", "Pre Sales (1)", "Pre Sales (2)",
    "Booking Link Shared", "Appointment Booked", "Post Consultation",
    "No Show", "Initial Requested", "Initial Received", "COE Received", "Won"
]

# --- THEME CSS ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Custom CSS for modern look and selective font size increase */
    html, body, [class*="css"] {{
        font-size: 102%; /* Subtle 2-point equivalent increase */
        font-family: 'Inter', sans-serif !important;
    }}
    .stApp {{
        background: {bg_color};
        color: {text_color};
    }}

    /* Block container */
    .block-container {{ max-width: 100% !important; padding: 1.5rem 2rem !important; }}

    /* ===== SIDEBAR ===== */
    [data-testid="stSidebar"] {{
        background-color: #1a1c1e !important;
        border-right: 1px solid #2d2f31 !important;
    }}
    [data-testid="stSidebar"] * {{
        color: #e2e8f0 !important;
        font-family: 'Inter', sans-serif !important;
    }}
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
        color: #94a3b8 !important;
        font-size: 0.72rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-weight: 600 !important;
    }}
    [data-testid="stSidebar"] .stSelectbox > div > div,
    [data-testid="stSidebar"] .stDateInput input {{
        background-color: #2d2f31 !important;
        border: 1px solid #3d4044 !important;
        border-radius: 6px !important;
        color: white !important;
    }}
    /* Sidebar logo strip at top */
    [data-testid="stSidebar"]::before {{
        content: '';
        display: block;
        height: 4px;
        background: {accent};
        margin-bottom: 1.5rem;
        border-radius: 0;
    }}

    div[data-baseweb="tab-list"] button p {{
        color: {secondary_text} !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
    }}
    div[data-baseweb="tab-list"] button[aria-selected="true"] p {{
        color: {text_color} !important;
        font-weight: 700 !important;
    }}
    div[data-baseweb="tab-list"] button[aria-selected="true"] {{
        border-bottom: 2px solid {accent} !important;
    }}

    /* ===== SECTION HEADERS ===== */
    h2, h3, .stSubheader > div {{
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        color: {text_color} !important;
    }}
    .stSubheader > div::after {{
        content: '';
        display: block;
        height: 2px;
        width: 32px;
        background: {accent};
        border-radius: 2px;
        margin-top: 6px;
    }}

    /* ===== BRAND HEADER ===== */
    .brand-header {{
        background: {accent}; /* Changed from sidebar_bg to accent as requested */
    padding: 1.5rem 2.5rem;
    border-radius: 16px;
    border-left: 6px solid #1a1c1e !important; /* Contrasting border */
    margin-bottom: 2rem;
    }}
    .brand-header h1 {{
        color: white !important;
        font-size: 1.6rem;
        font-weight: 600;
        font-family: 'Inter', sans-serif !important;
    }}
    .brand-header p {{ color: #94a3b8 !important; font-size: 0.9rem; margin-top: 0.4rem; }}

    /* ===== TABLES / DATAFRAMES ===== */
    [data-testid="stDataFrame"], [data-testid="stDataFrame"] > div {{
        background-color: {table_bg} !important;
        border-radius: 8px;
    }}
    [data-testid="stDataFrame"] div[role="grid"] {{ background-color: {table_bg} !important; }}
    [data-testid="stDataFrame"] div[role="columnheader"] p {{
        color: {secondary_text} !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        font-weight: 600 !important;
        letter-spacing: 0.05em !important;
    }}
    [data-testid="stDataFrame"] div[role="cell"] p {{ color: {text_color} !important; }}

    /* ===== SEPARATORS ===== */
    hr {{ border-color: {border_color} !important; margin: 1.5rem 0 !important; }}

    /* ===== SCROLLBAR ===== */
    ::-webkit-scrollbar {{ width: 6px; background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: {border_color}; border-radius: 4px; }}

    /* ===== STATUS BADGES ===== */
    .status-active {{ background:#dcfce7; color:#166534; padding:3px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; }}
    .status-inactive {{ background:#fee2e2; color:#991b1b; padding:3px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; }}
    </style>
""", unsafe_allow_html=True)

# --- DATA LOADING FUNCTIONS ---
@st.cache_data(ttl=600)
def load_pipeline_data():
    """Load opportunities data from local CSV"""
    data = {'opportunities': pd.DataFrame()}
    opps_file = "ghl/applications_tab_2025-11-01_to_2026-02-26.csv"
    if os.path.exists(opps_file):
        df = pd.read_csv(opps_file)
        if 'Created on (AEDT)' in df.columns:
            df['Created Date'] = pd.to_datetime(df['Created on (AEDT)'], errors='coerce').dt.date
        if 'Stage No' in df.columns:
            df['Stage Percentage'] = df['Stage No'].apply(convert_stage_no_to_percentage)
        data['opportunities'] = df
        print(f"Loaded {len(df)} opportunities from file")
    return data

@st.cache_data(ttl=600)
def load_contact_data():
    """Load contacts data from local CSV (full dataset)"""
    data = {'contacts': pd.DataFrame()}
    contacts_file = "ghl/detailed_contacts_full.csv"
    if os.path.exists(contacts_file):
        df = pd.read_csv(contacts_file)
        df.columns = df.columns.astype(str).str.strip()
        # Defensive Mapping: Ensure these specific columns are lowercase for the dashboard logic
        for col in df.columns:
            if col.lower() in ['country', 'city', 'first_attribution', 'latest_attribution', 'source']:
                df.rename(columns={col: col.lower()}, inplace=True)
        
        if 'Created (AEDT)' in df.columns:
            df['Created Date'] = pd.to_datetime(df['Created (AEDT)'], errors='coerce').dt.date
        elif 'contact_created' in df.columns:
            df['Created Date'] = pd.to_datetime(df['contact_created'], errors='coerce').dt.date
        data['contacts'] = df
        print(f"Loaded {len(df)} contacts from full file")
    return data

@st.cache_data(ttl=600)
def load_consultant_data():
    """Load consultant capacity data"""
    data = {'consultants_today': pd.DataFrame(), 'consultants_weekly': pd.DataFrame()}
    consult_today = "ghl/consultant_capacity_today.csv"
    if os.path.exists(consult_today):
        data['consultants_today'] = pd.read_csv(consult_today)
    consult_weekly = "ghl/consultant_capacity_weekly.csv"
    if os.path.exists(consult_weekly):
        data['consultants_weekly'] = pd.read_csv(consult_weekly)
    return data

# --- GSC FUNCTIONS ---
@st.cache_data(ttl=600)
def fetch_meta_aggregated(start, end):
    """Fetches high-level aggregated data by country - fast."""
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
        insights = account.get_insights(fields=fields, params=params)
        return process_meta_insights(insights)
    except Exception as e:
        st.error(f"Error fetching aggregated Meta data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def fetch_meta_daily(start, end):
    """Fetches granular daily data - slower, used for Fatigue/Decay."""
    try:
        FacebookAdsApi.init(APP_ID, APP_SECRET, ACCESS_TOKEN)
        account = AdAccount(AD_ACCOUNT_ID)
        fields = ['campaign_id', 'campaign_name', 'impressions', 'spend', 'inline_link_clicks', 'inline_link_click_ctr', 'actions']
        params = {
            'level': 'campaign',
            'time_range': {'since': start.strftime('%Y-%m-%d'), 'until': end.strftime('%Y-%m-%d')},
            'time_increment': 1,
            'filtering': [{'field': 'campaign.effective_status', 'operator': 'IN', 'value': ['ACTIVE', 'PAUSED']}],
            'breakdowns': ['country']
        }
        insights = account.get_insights(fields=fields, params=params)
        return process_meta_insights(insights)
    except Exception as e:
        st.error(f"Error fetching daily Meta data: {e}")
        return pd.DataFrame()

def process_meta_insights(insights):
    data = []
    columns = [
        'Date', 'Campaign', 'Country', 'Results', 'Reach', 'Frequency', 'Amount spent', 
        'Impressions', 'Link clicks', 'CTR (link click-through rate)', 'Outbound clicks', 
        'Outbound CTR', 'Landing page views', 'Result Rate Raw', '3s Hold', '50% Hook', 
        '95% Hook', 'Thruplays', 'CTR (all)', '_actions'
    ]
    
    for entry in insights:
        actions = entry.get('actions', [])
        video_actions = entry.get('video_thruplay_watched_actions', [])
        cost_per = entry.get('cost_per_action_type', [])
        
        def get_act(name):
            for a in actions:
                if a['action_type'] == name: return float(a['value'])
            return 0
            
        # --- RESULTS LOGIC (Align with gsc.py "Correct" logic) ---
        lead_forms = get_act('lead')
        web_conversions = (
            get_act('offsite_conversion.fb_pixel_submit_application') + 
            get_act('offsite_conversion.fb_pixel_lead') + 
            get_act('offsite_conversion.fb_pixel_purchase')
        )
        
        # Fallback for web conversions
        if web_conversions == 0 and lead_forms == 0:
            web_conversions = sum(float(a['value']) for a in actions if 'offsite_conversion' in a['action_type'])

        results_total = lead_forms + web_conversions
        # gsc.py logic: if lead_forms exist, use them; else use results_total
        final_results = int(lead_forms if lead_forms > 0 else results_total)
        
        def get_video_metric(field):
            val = entry.get(field, [])
            if isinstance(val, list) and len(val) > 0:
                return val[0].get('value', 0)
            return 0

        def get_thruplays():
            for a in actions:
                if a['action_type'] in ['video_thruplay', 'video_view_15_sec', 'video_played_to_completion']: 
                    return float(a['value'])
            for v in video_actions:
                if v['action_type'] in ['video_thruplay', 'video_view_15_sec', 'video_played_to_completion']:
                    return float(v['value'])
            return 0

        thruplays = int(get_thruplays())
        v_3s = int(get_act('video_view'))
        v_50 = int(get_video_metric('video_p50_watched_actions'))
        v_95 = int(get_video_metric('video_p95_watched_actions'))
        
        def get_outbound(entry_out):
            if isinstance(entry_out, list):
                for a in entry_out:
                    if a['action_type'] == 'outbound_click': return float(a['value'])
            return 0
        
        outbound_clicks = get_outbound(entry.get('outbound_clicks', []))

        # Store all relevant actions for the breakdown table
        relevant_actions = {a['action_type']: float(a['value']) for a in actions if any(x in a['action_type'].lower() for x in ['lead', 'regis', 'conv'])}

        data.append({
            'Date': entry.get('date_start', 'Total'),
            'Campaign': entry.get('campaign_name'), 'Country': entry.get('country', 'Unknown'), 
            'Results': final_results, 'Reach': entry.get('reach'),
            'Frequency': round(float(entry.get('frequency', 0)), 2), 
            'Amount spent': float(entry.get('spend', 0)),
            'Impressions': int(entry.get('impressions', 0)), 
            'Link clicks': int(entry.get('inline_link_clicks', 0)), 
            'CTR (link click-through rate)': float(entry.get('inline_link_click_ctr', 0)),
            'Outbound clicks': int(outbound_clicks),
            'Outbound CTR': (outbound_clicks / float(entry.get('impressions', 1)))*100 if int(entry.get('impressions', 0)) > 0 else 0,
            'Landing page views': int(get_act('landing_page_view')),
            'Result Rate Raw': (final_results/float(entry.get('impressions', 1))) if int(entry.get('impressions', 0)) > 0 else 0,
            '3s Hold': v_3s, '50% Hook': v_50, '95% Hook': v_95, 'Thruplays': thruplays,
            'CTR (all)': float(entry.get('ctr', 0)),
            '_actions': relevant_actions 
        })
        
    return pd.DataFrame(data, columns=columns) if data else pd.DataFrame(columns=columns)

@st.cache_data(ttl=600)
def fetch_ga4_data(start, end):
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
        client = BetaAnalyticsDataClient()
        
        start_str = start.strftime('%Y-%m-%d')
        end_str = end.strftime('%Y-%m-%d')
        
        # 1. Main Metrics Report (from gsc.py, but with country added back for UI filtering)
        main_request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name="date"), Dimension(name="country")],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="sessions"),
                Metric(name="averageSessionDuration"),
                Metric(name="bounceRate"),
                Metric(name="newUsers"),
                Metric(name="totalUsers"),
                Metric(name="screenPageViews"),
                Metric(name="keyEvents")
            ],
            date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        )
        
        # 2. Channel Group Report
        channel_request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name="sessionDefaultChannelGroup"), Dimension(name="country")],
            metrics=[Metric(name="sessions"), Metric(name="keyEvents")],
            date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        )

        # 3. Geography Report
        geo_request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name="country")],
            metrics=[Metric(name="activeUsers"), Metric(name="sessions"), Metric(name="keyEvents")],
            date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
            limit=50
        )

        # 4. Page Titles (instead of general LP in gsc.py, we keep path/title for the UI tabs)
        title_request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name="pageTitle"), Dimension(name="country")],
            metrics=[Metric(name="screenPageViews"), Metric(name="activeUsers")],
            date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
            limit=500
        )

        # 5. Page Paths
        path_request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name="pagePath"), Dimension(name="country")],
            metrics=[Metric(name="screenPageViews"), Metric(name="activeUsers")],
            date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
            limit=500
        )

        return (
            client.run_report(main_request),
            client.run_report(channel_request),
            client.run_report(geo_request),
            client.run_report(title_request),
            client.run_report(path_request)
        )
    except Exception as e:
        st.error(f"GA4 Error: {e}")
        return None, None, None, None, None

@st.cache_data(ttl=600)
def fetch_gsc_data(start, end):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        credentials = service_account.Credentials.from_service_account_file(GSC_KEY_FILE)
        service = build('searchconsole', 'v1', credentials=credentials)
        
        start_date = start.strftime('%Y-%m-%d')
        end_date = end.strftime('%Y-%m-%d')

        # 1. Total Stats & Trend (+ Country for UI filtering)
        trend_request = {'startDate': start_date, 'endDate': end_date, 'dimensions': ['date', 'country'], 'rowLimit': 5000}
        # 2. Query (+ Country)
        query_request = {'startDate': start_date, 'endDate': end_date, 'dimensions': ['query', 'country'], 'rowLimit': 1000}
        # 3. Page (+ Country)
        page_request = {'startDate': start_date, 'endDate': end_date, 'dimensions': ['page', 'country'], 'rowLimit': 1000}
        # 4. Global Countries
        country_request = {'startDate': start_date, 'endDate': end_date, 'dimensions': ['country'], 'rowLimit': 50}
        # 5. Query Trend for Sparklines (+ Country)
        spark_request = {'startDate': start_date, 'endDate': end_date, 'dimensions': ['date', 'query', 'country'], 'rowLimit': 5000}
        
        trend_res = service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=trend_request).execute()
        query_res = service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=query_request).execute()
        page_res = service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=page_request).execute()
        country_res = service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=country_request).execute()
        spark_res = service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=spark_request).execute()
        
        return trend_res.get('rows', []), query_res.get('rows', []), page_res.get('rows', []), country_res.get('rows', []), spark_res.get('rows', [])
    except Exception as e:
        st.error(f"GSC Error: {e}")
        return [], [], [], [], []

# --- SIDEBAR ---
with st.sidebar:
    # Logo section - "The Migration" in white bold
    st.markdown("""
        <div style="padding: 0.5rem 0 1.5rem; border-bottom: 1px solid #2d2f31; margin-bottom: 1.5rem;">
            <span style="color: white; font-weight: bold; font-size: 1.5rem;">The Migration</span>
        </div>
    """, unsafe_allow_html=True)
    
    
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    
    # Date Range without label (removed "Date Range" subheader)
    date_range = st.date_input("Select Range", [datetime(2025, 11, 1), datetime.now()], key="main_date_range_picker")
    
    # Appearance moved to bottom
    st.markdown("<div style='margin-top: auto; padding-top: 1rem; border-top: 1px solid #2d2f31;'></div>", unsafe_allow_html=True)
    choice = st.radio("Appearance", ["Light", "Dark"], key="theme_radio_main")
    if choice != st.session_state.theme_choice:
        st.session_state.theme_choice = choice
        st.rerun()

# --- MAIN RENDER ---
st.markdown(f"""
    <div class="brand-header" style="text-align: left; padding: 2rem 2.5rem;">
        <h1 style="font-size: 2.5rem; color: white !important;">Marketing Performance Intelligence</h1>
        <p style="color: rgba(255,255,255,0.8) !important;"></p>
    </div>
""", unsafe_allow_html=True)

# Load all data
pipeline_data = load_pipeline_data()
contact_data = load_contact_data()
consultant_data = load_consultant_data()

# --- TABS ---
tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎯 Our Vision", "📊 Ads & Creatives", "📈 Traffic Behaviour", 
    "🔍 SEO Performance", "💼 Pipeline Analysis", "👥 Attribution Analysis", "👨‍🏫 Consultant Capacity"
])

# === TAB 0: OUR VISION ===
with tab0:
    st.markdown("### Strategic Alignment")
    c1, c2, c3, c4 = st.columns(4)
    with c1: okr_scorecard("Current Clients", "344")
    with c2: okr_scorecard("Target Clients", "1,900")
    with c3: okr_scorecard("Growth Required", "452%")
    with c4: okr_scorecard("Cultures Connected", "6", color="#f6ad55")
    st.write("##")
    v1, v2 = st.columns(2)
    v1.markdown(f"<div style='border-left: 5px solid #00b4d8; padding: 20px; background: {surface_color}; height: 120px;'><b>VISION</b><br><small>To be the world's most trusted migration partner...</small></div>", unsafe_allow_html=True)
    v2.markdown(f"<div style='border-left: 5px solid #8b5cfc; padding: 20px; background: {surface_color}; height: 120px;'><b>MISSION</b><br><small>Solving migration challenges with transparency and accuracy...</small></div>", unsafe_allow_html=True)

# === TAB 1: ADS & CREATIVES ===
with tab1:
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        # 1. FAST KPI FETCH
        df_agg_raw = fetch_meta_aggregated(date_range[0], date_range[1])
        
        if not df_agg_raw.empty:
            # --- TOP CONTROL BAR ---
            all_meta_countries = sorted(df_agg_raw['Country'].unique())
            ctrl_c1, ctrl_c2 = st.columns([3, 1])
            with ctrl_c1:
                selected_meta_countries = st.multiselect("Filter by Country", all_meta_countries, default=all_meta_countries[:5] if len(all_meta_countries) > 5 else all_meta_countries)
            with ctrl_c2:
                meta_comparison_mode = st.toggle("Side-by-Side Comparison")

            df_agg_filt = df_agg_raw[df_agg_raw['Country'].isin(selected_meta_countries)].copy() if selected_meta_countries else df_agg_raw.copy()
            
            # --- 1. PRIMARY SCORECARDS ---
            st.markdown("### **1. Performance KPIs**")
            total_spend = df_agg_filt['Amount spent'].sum()
            total_leads = df_agg_filt['Results'].sum()
            avg_cpl = total_spend / total_leads if total_leads > 0 else 0
            total_links = df_agg_filt['Link clicks'].sum()
            avg_ctr_link = df_agg_filt['CTR (link click-through rate)'].mean()
            total_outbound = df_agg_filt['Outbound clicks'].sum()
            avg_ctr_out = (total_outbound / df_agg_filt['Impressions'].sum() * 100) if df_agg_filt['Impressions'].sum() > 0 else 0
            
            k1, k2, k3 = st.columns(3)
            with k1: okr_scorecard("Total Spend", f"${total_spend:,.0f}")
            with k2: okr_scorecard("Total Leads", f"{int(total_leads):,}")
            with k3: okr_scorecard("Avg. CPL", f"${avg_cpl:.2f}")
            
            k4, k5, k6 = st.columns(3)
            with k4: okr_scorecard("Link Clicks", f"{int(total_links):,}")
            with k5: okr_scorecard("Outbound CTR", f"{avg_ctr_out:.2f}%")
            with k6: okr_scorecard("Link CTR", f"{avg_ctr_link:.2f}%")

            st.divider()

            # --- 2. GENERAL VIDEO METRICS ---
            st.markdown("### **2. Creative Engagement (Hook & Hold)**")
            total_impr = df_agg_filt['Impressions'].sum()
            hook_rate = (df_agg_filt['3s Hold'].sum() / total_impr * 100) if total_impr > 0 else 0
            hold_rate = (df_agg_filt['Thruplays'].sum() / total_impr * 100) if total_impr > 0 else 0
            
            vh1, vh2 = st.columns(2)
            with vh1: okr_scorecard("Hook Rate (3s/Impr)", f"{hook_rate:.1f}%")
            with vh2: okr_scorecard("Hold Rate (Thru/Impr)", f"{hold_rate:.1f}%")

            st.divider()

            # --- 3. VIDEO RETENTION PIPELINE (HORIZONTAL) ---
            st.markdown("### **3. Video Retention Pipeline**")
            v_metrics = ['3s Hold', '50% Hook', '95% Hook', 'Thruplays']
            v_counts = [df_agg_filt[m].sum() for m in v_metrics]
            fig_hook = px.bar(x=v_counts, y=v_metrics, orientation='h', title="General Retention Pipeline (Total Views)", color_discrete_sequence=[accent])
            st.plotly_chart(apply_custom_chart_style(fig_hook), use_container_width=True)

            st.divider()

            # --- 4. CAMPAIGN PERFORMANCE ANALYSIS ---
            st.markdown("### **4. Campaign Performance Analysis**")
            # CTR% vs Frequency
            fatigue_df = df_agg_filt.copy()
            fatigue_df['Frequency'] = pd.to_numeric(fatigue_df['Frequency'], errors='coerce')
            fatigue_df = fatigue_df[fatigue_df['Frequency'] > 0]
            
            if not fatigue_df.empty:
                import statsmodels.api as sm
                fig_fatigue = px.scatter(fatigue_df, x="Frequency", y="CTR (link click-through rate)", 
                                         size="Amount spent", color="Campaign", hover_name="Campaign",
                                         trendline="ols", trendline_color_override="red",
                                         title="Campaign Performance Analysis: CTR% vs. Frequency")
                st.plotly_chart(apply_custom_chart_style(fig_fatigue), use_container_width=True)
            else:
                st.info("Insufficient frequency data for regression.")

            st.divider()

            # --- 5. STRATEGIC CORRELATION ANALYSIS ---
            st.markdown("### **5. Strategic Performance Correlation**")
            # CTR% vs Result Rate%
            df_agg_filt['Result Rate (%)'] = (df_agg_filt['Results'] / df_agg_filt['Impressions'] * 100).fillna(0)
            fig_strategic = px.scatter(df_agg_filt, x="CTR (link click-through rate)", y="Result Rate (%)",
                                       size="Results", color="Campaign", hover_name="Campaign",
                                       title="Messaging Relevance vs. Conversion Intent")
            st.plotly_chart(apply_custom_chart_style(fig_strategic), use_container_width=True)

            st.divider()

            # --- 6. ENGAGEMENT-TO-CONVERSION DECAY ---
            st.markdown("### **6. Engagement-to-Conversion Decay**")
            with st.spinner("Analyzing conversion decay..."):
                df_daily_raw = fetch_meta_daily(date_range[0], date_range[1])
                if not df_daily_raw.empty:
                    df_d_filt = df_daily_raw[df_daily_raw['Country'].isin(selected_meta_countries)] if selected_meta_countries else df_daily_raw
                    if df_d_filt['Date'].nunique() > 14:
                        df_d_filt['Date_DT'] = pd.to_datetime(df_d_filt['Date'])
                        min_d = df_d_filt['Date_DT'].min()
                        c1_d = df_d_filt[df_d_filt['Date_DT'] < min_d + pd.Timedelta(days=7)]
                        c2_d = df_d_filt[df_d_filt['Date_DT'] > min_d + pd.Timedelta(days=14)]
                        rr1, rr2 = c1_d['Result Rate Raw'].mean()*100, c2_d['Result Rate Raw'].mean()*100
                        d_col1, d_col2 = st.columns(2)
                        with d_col1: okr_scorecard("Result Rate (D1-7)", f"{rr1:.2f}%")
                        with d_col2: okr_scorecard("Result Rate (D14-21)", f"{rr2:.2f}%", delta=f"{rr2-rr1:.2f}%")
                    else: st.warning("Min 14 days required for decay check.")

            st.divider()

            # --- 7. LANDING PAGE DROP-OFF ---
            st.markdown("### **7. Landing Page Health**")
            total_lp = df_agg_filt['Landing page views'].sum()
            drop_off = (1 - total_lp / total_links) * 100 if total_links > 0 else 0
            st.markdown(f"#### Landing Page Drop-off Rate: **{drop_off:.1f}%**")
            if drop_off > 60: st.warning("⚠️ Warning: High drop-off rate. Potential relevancy or speed issue.")
            else: st.success("✅ Health: Drop-off rate is looking good.")

            st.divider()

            # --- 8. CONVERSION BREAKDOWN ---
            st.markdown("### **8. Conversion Type Breakdown**")
            with st.expander("🔍 View All Conversion Actions", expanded=False):
                # Aggregate all actions from the filtered dataframe
                all_actions_combined = {}
                for action_map in df_agg_filt['_actions']:
                    for atype, val in action_map.items():
                        all_actions_combined[atype] = all_actions_combined.get(atype, 0) + val
                
                if all_actions_combined:
                    df_breakdown = pd.DataFrame(list(all_actions_combined.items()), columns=['Conversion Type', 'Count']).sort_values('Count', ascending=False)
                    st.dataframe(df_breakdown, use_container_width=True, hide_index=True)
                else:
                    st.info("No specific action data found.")

            st.divider()

            # --- 9. META CAMPAIGNS ---
            st.markdown("### **9. Meta Campaigns**")
            # Precise aggregation for the table
            agg_rules = {
                'Amount spent': 'sum', 'Results': 'sum', 'Impressions': 'sum', 
                'Link clicks': 'sum', '3s Hold': 'sum', 'Thruplays': 'sum',
                'CTR (link click-through rate)': 'mean', 'CTR (all)': 'mean', 'Frequency': 'mean'
            }
            # Add other metrics if they exist
            found_cols = [c for c in agg_rules.keys() if c in df_agg_filt.columns]
            df_agg_final = df_agg_filt.groupby(['Campaign', 'Country']).agg({c: agg_rules[c] for c in found_cols}).reset_index()

            with st.expander("📂 View Detailed Campaigns", expanded=True):
                st.dataframe(df_agg_final.style.set_properties(**{'font-weight': 'bold'}), use_container_width=True)
                csv = df_agg_final.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Report", data=csv, file_name="meta_report.csv")
# === TAB 2: TRAFFIC BEHAVIOUR ===
with tab2:
    main_res, chan_res, geo_res, title_res, path_res = fetch_ga4_data(date_range[0], date_range[1])
    if main_res:
        # --- 0. CONTROL BAR ---
        geo_data_all = [{"Country": r.dimension_values[0].value, "Users": int(r.metric_values[0].value)} for r in geo_res.rows]
        df_geo_all = pd.DataFrame(geo_data_all)
        all_ga4_countries = sorted(df_geo_all['Country'].unique())
        
        col_ctrl1, col_ctrl2 = st.columns([3, 1])
        with col_ctrl1:
            selected_ga4_countries = st.multiselect("Filter by Country", all_ga4_countries, 
                                                     default=all_ga4_countries[:5] if len(all_ga4_countries) > 5 else all_ga4_countries, key="ga4_country_filter_new")
        with col_ctrl2:
            ga4_comparison_mode = st.toggle("Side-by-Side Comparison", key="ga4_comp_toggle")

        def filter_ga4_rows(rows, selected_countries, country_dim_idx=1):
            if not selected_countries: return rows
            return [r for r in rows if r.dimension_values[country_dim_idx].value in selected_countries]

        def process_main_df(rows):
            data = []
            for r in rows:
                data.append({
                    "Date": pd.to_datetime(r.dimension_values[0].value),
                    "Active Users": int(r.metric_values[0].value),
                    "Sessions": int(r.metric_values[1].value),
                    "Avg Duration": float(r.metric_values[2].value),
                    "Bounce Rate": float(r.metric_values[3].value),
                    "New Users": int(r.metric_values[4].value),
                    "Total Users": int(r.metric_values[5].value),
                    "Views": int(r.metric_values[6].value),
                    "Key Events": int(r.metric_values[7].value)
                })
            return pd.DataFrame(data).sort_values("Date") if data else pd.DataFrame()

        def render_ga4_content(countries_to_show, title_prefix=""):
            f_main = filter_ga4_rows(main_res.rows, countries_to_show, 1)
            f_chan = filter_ga4_rows(chan_res.rows, countries_to_show, 1)
            f_title = filter_ga4_rows(title_res.rows, countries_to_show, 1)
            f_path = filter_ga4_rows(path_res.rows, countries_to_show, 1)
            df_m = process_main_df(f_main)
            
            if df_m.empty:
                st.info(f"No data available for {title_prefix or 'selected filters'}")
                return

            # 1. ENGAGEMENT OVERVIEW
            st.markdown(f"### {title_prefix} **1. Engagement Overview**")
            t_active = df_m["Active Users"].sum()
            t_sessions = df_m["Sessions"].sum()
            t_views = df_m["Views"].sum()
            t_events = df_m["Key Events"].sum()
            a_bounce = df_m["Bounce Rate"].mean()
            
            k_cols = st.columns(5) if not ga4_comparison_mode else st.columns(3)
            with k_cols[0]: okr_scorecard("Active Users", f"{t_active:,}")
            with k_cols[1]: okr_scorecard("Sessions", f"{t_sessions:,}")
            if not ga4_comparison_mode:
                with k_cols[2]: okr_scorecard("Views", f"{t_views:,}")
                with k_cols[3]: okr_scorecard("Key Events", f"{t_events:,}", color="#10b981")
                with k_cols[4]: okr_scorecard("Bounce Rate", f"{a_bounce*100:.1f}%", color="#ef4444")
            else:
                with k_cols[2]: okr_scorecard("Key Events", f"{t_events:,}", color="#10b981")

            st.markdown("#### **User Engagement Trend**")
            # 7-day Moving Average for Smoothing
            if len(df_m) >= 7:
                df_m["Smooth Users"] = df_m["Active Users"].rolling(window=7, min_periods=1).mean()
                fig_t = px.area(df_m, x="Date", y="Smooth Users", 
                                title=f"User Engagement Trend (7-Day Moving Avg) {'('+title_prefix+')' if title_prefix else ''}",
                                color_discrete_sequence=["#2dd4bf"]) # Teal
                fig_t.update_traces(line=dict(width=4, shape='spline'), fillcolor='rgba(45, 212, 191, 0.2)')
            else:
                fig_t = px.area(df_m, x="Date", y="Active Users", title=f"Daily Active Users Trend", color_discrete_sequence=["#2dd4bf"])
            st.plotly_chart(apply_custom_chart_style(fig_t), use_container_width=True)

            # 2. USER ACQUISITION
            st.markdown(f"### {title_prefix} **2. User Acquisition: Channel Trends**")
            c_data = []
            for r in f_chan:
                c_data.append({"Channel": r.dimension_values[0].value, "Sessions": int(r.metric_values[0].value)})
            df_c = pd.DataFrame(c_data).groupby("Channel").sum().reset_index() if c_data else pd.DataFrame()
            if not df_c.empty:
                fig_c = px.bar(df_c.sort_values("Sessions", ascending=False), x="Channel", y="Sessions", color="Channel", title="Sessions by Channel Group")
                st.plotly_chart(apply_custom_chart_style(fig_c), use_container_width=True)

            if not title_prefix:
                # 3. TRAFFIC BY COUNTRY
                st.markdown("### **3. Traffic by Country**")
                df_g = df_geo_all[df_geo_all['Country'].isin(countries_to_show)] if countries_to_show else df_geo_all
                df_g = df_g.sort_values("Users", ascending=False).head(10)
                g1, g2 = st.columns([1, 2])
                with g1: st.dataframe(df_g, use_container_width=True, hide_index=True)
                with g2: 
                    fig_g = px.pie(df_g, values="Users", names="Country", hole=0.4, title="User Distribution")
                    st.plotly_chart(apply_custom_chart_style(fig_g), use_container_width=True)

            # 4. KEY EVENTS BEHAVIOUR
            st.markdown(f"### {title_prefix} **4. Key Events Behaviour**")
            # 7-day Moving Average for Smoothing (consistent with Engagement Trend)
            if len(df_m) >= 7:
                df_m["Smooth Events"] = df_m["Key Events"].rolling(window=7, min_periods=1).mean()
                fig_key = px.area(df_m, x="Date", y="Smooth Events", 
                                title=f"Key Events Trend (7-Day Moving Avg) {'('+title_prefix+')' if title_prefix else ''}",
                                color_discrete_sequence=["#2dd4bf"]) # Teal
                fig_key.update_traces(line=dict(width=4, shape='spline'), fillcolor='rgba(45, 212, 191, 0.2)')
            else:
                fig_key = px.area(df_m, x="Date", y="Key Events", title="Daily Key Events Trend", color_discrete_sequence=["#2dd4bf"])
            
            st.plotly_chart(apply_custom_chart_style(fig_key), use_container_width=True)

            # 5. PAGE PERFORMANCE
            st.markdown(f"### {title_prefix} **5. Page Performance Analysis**")
            p1, p2 = st.columns(2) if not ga4_comparison_mode else (st.container(), st.container())
            with p1:
                st.markdown("#### Views by Page title")
                t_list = [{"Page Title": r.dimension_values[0].value, "Views": int(r.metric_values[0].value), "Users": int(r.metric_values[1].value)} for r in f_title]
                df_t = pd.DataFrame(t_list).groupby("Page Title").sum().reset_index().sort_values("Views", ascending=False).head(10) if t_list else pd.DataFrame()
                st.dataframe(df_t.style.set_properties(**{'font-weight': 'bold'}), use_container_width=True, hide_index=True)
            with p2:
                st.markdown("#### Top 10 Page paths")
                path_list = [{"Page Path": r.dimension_values[0].value, "Views": int(r.metric_values[0].value)} for r in f_path]
                df_p = pd.DataFrame(path_list).groupby("Page Path").sum().reset_index().sort_values("Views", ascending=False).head(10) if path_list else pd.DataFrame()
                st.dataframe(df_p.style.set_properties(**{'font-weight': 'bold'}), use_container_width=True, hide_index=True)

        if ga4_comparison_mode and len(selected_ga4_countries) == 2:
            c1, c2 = selected_ga4_countries[0], selected_ga4_countries[1]
            st.markdown(f"## ⚔️ Comparison: {c1} vs {c2}")
            col_a, col_b = st.columns(2)
            with col_a: render_ga4_content([c1], f"📊 {c1}")
            with col_b: render_ga4_content([c2], f"📊 {c2}")
        else:
            render_ga4_content(selected_ga4_countries)

# === TAB 3: SEO PERFORMANCE ===
with tab3:
    gsc_trend, gsc_queries, gsc_pages, gsc_countries, gsc_spark = fetch_gsc_data(date_range[0], date_range[1])
    
    if gsc_countries:
        # --- 0. CONTROL BAR ---
        geo_gsc_all = [{"Country": r['keys'][0], "Clicks": r['clicks'], "Impressions": r['impressions']} for r in gsc_countries]
        df_geo_gsc_all = pd.DataFrame(geo_gsc_all)
        all_seo_countries = sorted(df_geo_gsc_all['Country'].unique())
        
        c_ctrl1, c_ctrl2 = st.columns([3, 1])
        with c_ctrl1:
            selected_seo_countries = st.multiselect("Filter by Country", all_seo_countries, 
                                                 default=all_seo_countries[:5] if len(all_seo_countries) > 5 else all_seo_countries, key="seo_country_filter_new")
        with c_ctrl2:
            seo_comparison_mode = st.toggle("Side-by-Side Comparison", key="seo_comp_toggle")

        def filter_gsc(rows, selected_countries, country_idx=1):
            if not selected_countries: return rows
            return [r for r in rows if r['keys'][country_idx] in selected_countries]

        def render_seo_content(countries_to_show, title_prefix=""):
            f_trend = filter_gsc(gsc_trend, countries_to_show, 1)
            f_queries = filter_gsc(gsc_queries, countries_to_show, 1)
            f_pages = filter_gsc(gsc_pages, countries_to_show, 1)
            
            # 1. Performance KPI's
            st.markdown(f"### {title_prefix} **1. Performance KPI's**")
            df_t = pd.DataFrame([{'Clicks': r['clicks'], 'Impressions': r['impressions'], 'Position': r['position']} for r in f_trend])
            if not df_t.empty:
                t_clicks = df_t['Clicks'].sum()
                t_impr = df_t['Impressions'].sum()
                a_ctr = (t_clicks / t_impr * 100) if t_impr > 0 else 0
                a_pos = df_t['Position'].mean()
                
                k_cols = st.columns(4)
                with k_cols[0]: okr_scorecard("Total Clicks", f"{int(t_clicks):,}")
                with k_cols[1]: okr_scorecard("Total Impressions", f"{int(t_impr):,}")
                with k_cols[2]: okr_scorecard("Avg. CTR", f"{a_ctr:.2f}%")
                with k_cols[3]: okr_scorecard("Avg. Position", f"{a_pos:.1f}")
            
            # 2. Performance Chart
            st.markdown(f"### {title_prefix} **2. Performance**")
            df_t_grp = pd.DataFrame([{'Date': r['keys'][0], 'Clicks': r['clicks'], 'Impressions': r['impressions']} for r in f_trend]).groupby('Date').sum().reset_index().sort_values('Date')
            if not df_t_grp.empty:
                fig_p = go.Figure()
                fig_p.add_trace(go.Scatter(x=df_t_grp['Date'], y=df_t_grp['Clicks'], name="Clicks", line=dict(color=accent, width=3), fill='tozeroy'))
                fig_p.add_trace(go.Scatter(x=df_t_grp['Date'], y=df_t_grp['Impressions'], name="Impressions", line=dict(color="#8b5cfc", width=2, dash='dot'), yaxis="y2"))
                fig_p.update_layout(height=400, yaxis=dict(title="Clicks", color=accent), yaxis2=dict(title="Impressions", overlaying='y', side='right', color='#8b5cfc'), 
                                    margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified", legend=dict(orientation="h", y=1.1, x=1, xanchor='right'))
                st.plotly_chart(apply_custom_chart_style(fig_p), use_container_width=True)

            # 3. Golden Opportunity Matrix
            st.markdown(f"### {title_prefix} **3. Golden Opportunity Matrix — Keyword Rankings**")
            df_q = pd.DataFrame([{'Keyword': r['keys'][0], 'Clicks': r['clicks'], 'Impressions': r['impressions'], 'CTR': r['ctr']*100, 'Avg Position': r['position']} for r in f_queries])
            if not df_q.empty:
                df_q = df_q.groupby('Keyword').agg({'Clicks': 'sum', 'Impressions': 'sum', 'CTR': 'mean', 'Avg Position': 'mean'}).reset_index()
                df_q['Zone'] = df_q['Avg Position'].apply(lambda p: 'Top Ranking' if p < 5 else ('High Opportunity' if 5 <= p <= 15 else 'Monitoring'))
                color_map = {'Top Ranking': '#1e3a8a', 'High Opportunity': '#d97706', 'Monitoring': '#94a3b8'}
                
                fig_m = px.scatter(df_q, x="Avg Position", y="Impressions", size="Clicks", color="Zone", hover_name="Keyword",
                                   template=plotly_template, height=500, color_discrete_map=color_map,
                                   labels={"Avg Position": "Avg Position", "Impressions": "Impressions"},
                                   hover_data={"Avg Position": True, "Impressions": ':,', "Clicks": ':,', "CTR": ':.2f'})
                
                fig_m.add_vrect(x0=0, x1=5, fillcolor="#F0F8FF", opacity=0.15, layer="below", line_width=0)
                fig_m.add_vrect(x0=5, x1=15, fillcolor="#F7E7CE", opacity=0.2, layer="below", line_width=0, annotation_text="🎯 OPPORTUNITY ZONE", annotation_position="top left")

                fig_m.add_annotation(x=2.5, y=df_q['Impressions'].max()*0.9 if not df_q.empty else 0, text="<b>MAINTAIN</b>", showarrow=False, font=dict(size=14, color="#cbd5e1"), opacity=0.4)
                fig_m.add_annotation(x=10, y=df_q['Impressions'].max()*0.9 if not df_q.empty else 0, text="<b>SCALE NOW</b>", showarrow=False, font=dict(size=14, color="#cbd5e1"), opacity=0.4)
                fig_m.add_annotation(x=25, y=df_q['Impressions'].max()*0.9 if not df_q.empty else 0, text="<b>MONITOR</b>", showarrow=False, font=dict(size=14, color="#cbd5e1"), opacity=0.4)

                top3_opp = df_q[df_q['Zone']=='High Opportunity'].sort_values('Impressions', ascending=False).head(3)
                for _, row in top3_opp.iterrows():
                    fig_m.add_annotation(x=row['Avg Position'], y=row['Impressions'], text=row['Keyword'], showarrow=True, arrowhead=1, arrowsize=0.5, arrowcolor="#64748b", font=dict(size=10))

                fig_m.update_xaxes(autorange="reversed", showgrid=True, gridcolor="#f1f5f9", gridwidth=0.5, zeroline=False)
                fig_m.update_yaxes(showgrid=True, gridcolor="#f1f5f9", gridwidth=0.5, zeroline=False)
                fig_m.update_traces(marker=dict(line=dict(width=1, color='white'), opacity=0.8))
                fig_m.update_layout(paper_bgcolor=chart_bg, plot_bgcolor=chart_bg, font=dict(family="Inter, sans-serif", color=text_color),
                                    legend=dict(orientation="h", y=-0.2, x=0.5, xanchor='center'))
                st.plotly_chart(fig_m, use_container_width=True)

            # 4. Content Performance — Clicks vs CTR (Revenue Glow)
            st.markdown(f"### {title_prefix} **4. Content Performance — Clicks vs CTR**")
            df_p = pd.DataFrame([{'Page': r['keys'][0], 'Clicks': r['clicks'], 'CTR': r['ctr']*100} for r in f_pages])
            if not df_p.empty:
                df_p = df_p.groupby('Page').agg({'Clicks': 'sum', 'CTR': 'mean'}).reset_index().sort_values('Clicks', ascending=False).head(10)
                
                # Intent Gradient Color Mapping
                # Awareness (Cool Light Cyan) -> Engagement (Deep Electric Blue) -> Closing (Emerald Green)
                colors = ['#2dd4bf', '#3b82f6', '#10b981'] # Simplified mockup of the gradient
                
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(
                    y=df_p['Page'], x=df_p['Clicks'], orientation='h', name='Clicks',
                    marker=dict(
                        color=df_p['Clicks'],
                        colorscale=[[0, '#cffafe'], [0.5, '#3b82f6'], [1, '#10b981']], # Light Cyan -> Blue -> Emerald
                        line=dict(width=0), 
                        pattern_shape=""
                    ),
                    text=df_p['Clicks'], textposition='outside', textfont=dict(weight='bold'),
                    hovertemplate='<b>%{y}</b><br>Clicks: %{x}<extra></extra>'
                ))
                
                fig_bar.update_layout(
                    height=450, showlegend=False,
                    paper_bgcolor=chart_bg, plot_bgcolor=chart_bg,
                    margin=dict(l=20, r=40, t=20, b=20),
                    yaxis=dict(autorange="reversed", showgrid=False)
                )
                # Rounded corners (Plotly doesn't support them natively on bars easily, so we use a visual workaround or keep them clean)
                fig_bar.update_traces(marker_line_width=0, marker_pattern_fillmode="replace") 
                
                st.plotly_chart(fig_bar, use_container_width=True)

            # 5. Search Console Keyword Intelligence (Mirrored - No Formatting)
            st.markdown(f"### {title_prefix} **5. Search Console Keyword Intelligence**")
            if not df_q.empty:
                # Mirroring without formatting as requested
                mirror_df = df_q[['Keyword', 'Clicks', 'Impressions', 'CTR', 'Avg Position', 'Zone']].copy()
                mirror_df.columns = ['Keyword', 'Clicks', 'Impressions', 'CTR (%)', 'Avg Pos', 'Status']
                st.dataframe(mirror_df.sort_values('Clicks', ascending=False).head(20), use_container_width=True, hide_index=True)
            
        if seo_comparison_mode and len(selected_seo_countries) == 2:
            sc1, sc2 = selected_seo_countries[0], selected_seo_countries[1]
            st.markdown(f"## ⚔️ Comparison: {sc1} vs {sc2}")
            col_a, col_b = st.columns(2)
            with col_a: render_seo_content([sc1], f"📊 {sc1}")
            with col_b: render_seo_content([sc2], f"📊 {sc2}")
        else:
            render_seo_content(selected_seo_countries)
    

            













# === TAB 4: PIPELINE ANALYSIS ===
with tab4:
    st.header("💼 Pipeline Analysis")
    opps = pipeline_data['opportunities']
    if opps.empty:
        st.warning("No opportunity data available")
    else:
        # Handle date_range - ensure we have date objects
        start_date = date_range[0] if hasattr(date_range[0], 'date') else date_range[0]
        end_date = date_range[1] if hasattr(date_range[1], 'date') else date_range[1]
        
        if 'Created Date' in opps.columns:
            opps_filtered = opps[(opps['Created Date'] >= start_date) & (opps['Created Date'] <= end_date)].copy()
        else:
            opps_filtered = opps.copy()
        
        # Remove headings and text as requested
        # Geography Insights
        geo_col1, geo_col2 = st.columns([2, 1])
        with geo_col1:
            geo_type = st.radio("Group By", ["Country", "City"], horizontal=True, key="p_geo_type")
            geo_col = 'Current Country' if geo_type == "Country" else 'Current City'
            
            if geo_col in opps_filtered.columns:
                geo_options = sorted(opps_filtered[geo_col].dropna().unique())
                selected_geo = st.multiselect(f"Select {geo_type}(s)", ["All"] + geo_options, default="All", key="p_geo_val")
                if "All" not in selected_geo and selected_geo:
                    opps_filtered = opps_filtered[opps_filtered[geo_col].isin(selected_geo)]
        
        with geo_col2:
            p_comp_mode = st.toggle("Compare Selected", key="p_comp_toggle")
        
        st.markdown(f"<small>Records: {len(opps_filtered)} opportunities</small>", unsafe_allow_html=True)
        
        if p_comp_mode and "All" not in selected_geo and len(selected_geo) == 2:
            cc1, cc2 = selected_geo[0], selected_geo[1]
            st.markdown(f"#### ⚔️ Comparison: {cc1} vs {cc2}")
            p_cols = st.columns(2)
            for i, val in enumerate([cc1, cc2]):
                city_df = opps_filtered[opps_filtered[geo_col] == val]
                with p_cols[i]:
                    okr_scorecard(f"{val} Total", f"{len(city_df):,}", color=accent)
                    okr_scorecard(f"{val} Value", f"${city_df['Opportunity Value'].sum():,.0f}", color="#10b981")
            st.markdown("---")
        
        # Scorecards
        # 1. Pipeline KPI's
        total_val = opps_filtered['Opportunity Value'].sum() if 'Opportunity Value' in opps_filtered.columns else 0
        l2c_open_count = 0
        if 'Pipeline' in opps_filtered.columns and 'Status' in opps_filtered.columns:
            l2c_open_count = len(opps_filtered[(opps_filtered['Pipeline'] == 'L2C - Education') & (opps_filtered['Status'] == 'open')])

        k_cols = st.columns(3)
        with k_cols[0]: okr_scorecard("Total Opportunities", f"{len(opps_filtered):,}", color=accent)
        with k_cols[1]: okr_scorecard("Pipeline Value", f"${total_val:,.0f}", color="#10b981")
        with k_cols[2]: okr_scorecard("L2C Education (Open)", f"{l2c_open_count:,}", color="#8b5cfc")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # 2. Owner & Status Analysis
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            if 'Opportunity Owner' in opps_filtered.columns and 'Status' in opps_filtered.columns:
                # Group and get Top Owners
                owner_counts = opps_filtered.groupby('Opportunity Owner').size().reset_index(name='Total').sort_values('Total', ascending=False)
                top_15 = owner_counts.head(15)['Opportunity Owner'].tolist()
                
                df_owner = opps_filtered.copy()
                df_owner['Owner Display'] = df_owner['Opportunity Owner'].apply(lambda x: "".join([n[0] for n in str(x).split()]) if str(x) != 'nan' else 'U')
                df_owner['Owner Label'] = df_owner['Opportunity Owner'] + " (" + df_owner['Owner Display'] + ")"
                
                owner_status = df_owner.groupby(['Owner Label', 'Status']).size().reset_index(name='Count')
                # Traffic Light Palette: Won (Emerald), Open (Navy), Lost (Slate/Terracotta)
                p_colors = {'won': '#10b981', 'open': '#1e3a8a', 'lost': '#94a3b8', 'abandoned': '#64748b'}
                
                fig_o = px.bar(owner_status, x='Count', y='Owner Label', color='Status', orientation='h', 
                               color_discrete_map=p_colors, barmode='stack')
                
                fig_o.update_layout(
                    xaxis_type='log', # LOG SCALE to handle Unassigned
                    height=450, showlegend=True,
                    paper_bgcolor=chart_bg, plot_bgcolor=chart_bg,
                    margin=dict(l=20, r=20, t=20, b=20),
                    font=dict(family="Inter, sans-serif")
                )
                fig_o.update_traces(marker_line_width=0, opacity=0.9)
                st.plotly_chart(fig_o, use_container_width=True)
        
        with col_chart2:
            if 'Status' in opps_filtered.columns:
                status_counts = opps_filtered.groupby('Status').size().reset_index(name='Count').sort_values('Count', ascending=False)
                total_status = status_counts['Count'].sum()
                
                fig_s = px.pie(status_counts, values='Count', names='Status', hole=0.6,
                               color='Status', color_discrete_map=p_colors)
                
                fig_s.update_traces(textposition='outside', textinfo='percent+label', marker=dict(line=dict(color='white', width=2)))
                # CENTER TEXT
                fig_s.add_annotation(text=f"<b>{total_status:,}</b><br>Total", showarrow=False, font_size=20, font_family="Inter, sans-serif")
                
                fig_s.update_layout(height=450, showlegend=False, paper_bgcolor=chart_bg, font=dict(family="Inter, sans-serif", color=text_color))
                st.plotly_chart(fig_s, use_container_width=True)
        
        st.markdown("---")
        
        # 3. Phase-Based Pipeline Funnel
        st.markdown(f"### **3. Phase-Based Pipeline Funnel (L2C Education)**")
        if 'Pipeline' in opps_filtered.columns and 'Status' in opps_filtered.columns:
            l2c_df = opps_filtered[opps_filtered['Pipeline'] == 'L2C - Education'].copy()
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
                    # Calculate Conversion Rates for Badges
                    f_df['Prev Count'] = f_df['Count'].shift(1)
                    f_df['Conv Rate'] = (f_df['Count'] / f_df['Prev Count'] * 100).fillna(0)
                    
                    # Gradient of Intent: Soft Blue -> Royal Blue -> Emerald
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
                    
                    # Add Conversion Micro-Metrics (Badges)
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
                        paper_bgcolor=chart_bg, plot_bgcolor=chart_bg,
                        margin=dict(l=20, r=40, t=20, b=20),
                        yaxis=dict(autorange="reversed", showgrid=False)
                    )
                    st.plotly_chart(fig_f, use_container_width=True)
        
        st.markdown("---")
        
        # 4. Lead Source Analysis
        st.markdown(f"### **4. Lead Source Analysis**")
        if 'Lead Source' in opps_filtered.columns and 'Status' in opps_filtered.columns:
            lead_counts = opps_filtered.groupby('Lead Source').size().reset_index(name='Total').sort_values('Total', ascending=False)
            top_12 = lead_counts.head(12)['Lead Source'].tolist()
            
            df_lead = opps_filtered.copy()
            df_lead['Lead Category'] = df_lead['Lead Source'].apply(lambda x: x if x in top_12 else 'Others')
            lead_status = df_lead.groupby(['Lead Category', 'Status']).size().reset_index(name='Count')
            
            fig_l = px.bar(lead_status, x='Count', y='Lead Category', color='Status', orientation='h',
                           color_discrete_map=p_colors, barmode='stack')
            
            fig_l.update_layout(
                height=500, showlegend=True,
                paper_bgcolor=chart_bg, plot_bgcolor=chart_bg,
                margin=dict(l=20, r=20, t=10, b=10),
                font=dict(family="Inter, sans-serif"),
                xaxis=dict(showgrid=True, gridcolor=border_color)
            )
            fig_l.update_traces(marker_line_width=0, opacity=0.9)
            st.plotly_chart(fig_l, use_container_width=True)
        
        st.markdown("---")
        
        # 5. Opportunity Pipeline Bubble Chart (Executive View)
        st.markdown(f"### **5. Opportunity Pipeline Bubble Chart**")
        if 'Status' in opps_filtered.columns and 'Stage Percentage' in opps_filtered.columns:
            open_opps = opps_filtered[opps_filtered['Status'] == 'open'].copy()
            if not open_opps.empty and 'Lead Source' in open_opps.columns:
                bubble_data = open_opps.groupby('Lead Source').agg({'Opportunity Name': 'count', 'Opportunity Value': 'sum', 'Stage Percentage': 'mean'}).reset_index()
                bubble_data.columns = ['Lead Source', 'Count', 'Value', 'Avg Stage %']
                if not bubble_data.empty:
                    fig_b = px.scatter(bubble_data, x='Avg Stage %', y='Value', size='Count', color='Lead Source', 
                                     title="Lead Source Performance (Open Context)",
                                     color_discrete_sequence=['#1e3a8a', '#10b981', '#3b82f6', '#94a3b8', '#6366f1'],
                                     size_max=45)
                    
                    fig_b.update_layout(
                        height=500, paper_bgcolor=chart_bg, plot_bgcolor=chart_bg,
                        font=dict(family="Inter, sans-serif", color=text_color),
                        xaxis=dict(title="Stage Progress (%)", tickformat='.0f', gridcolor=border_color),
                        yaxis=dict(title="Pipeline Value ($)", gridcolor=border_color)
                    )
                    fig_b.update_traces(marker=dict(line=dict(width=1, color='white'), opacity=0.8))
                    st.plotly_chart(fig_b, use_container_width=True)
                    st.caption("Visual hierarchy: Bubble size = Opp Count | Color = Source | X = Progress")

# === TAB 5: ATTRIBUTION ANALYSIS ===
with tab5:
    contacts = contact_data['contacts']
    if contacts.empty:
        st.warning("No contact data available")
    else:
        # Removal of legacy headings as requested
        st.markdown("""<div style='margin-bottom: 1rem;'><b>ℹ️ Filter Applied:</b> This section uses Country/City filter below.</div>""", unsafe_allow_html=True)
        
        # Handle date_range for contacts - ensure we have date objects
        start_date_contact = date_range[0] if hasattr(date_range[0], 'date') else date_range[0]
        end_date_contact = date_range[1] if hasattr(date_range[1], 'date') else date_range[1]
        
        if 'Created Date' in contacts.columns:
            contacts_filtered = contacts[(contacts['Created Date'] >= start_date_contact) & (contacts['Created Date'] <= end_date_contact)].copy()
        else:
            contacts_filtered = contacts.copy()
        
        # Redesigned Location Filter & Comparison
        geo_col1, geo_col2 = st.columns([2, 1])
        with geo_col1:
            a_geo_type = st.radio("Group Attribution By", ["Country", "City"], horizontal=True, key="a_geo_type")
            a_geo_col = 'country' if a_geo_type == "Country" else 'city' # Using existing column names
            
            if a_geo_col in contacts_filtered.columns:
                a_options = sorted(contacts_filtered[a_geo_col].dropna().unique())
                selected_a_geo = st.multiselect(f"Select {a_geo_type}(s)", ["All"] + a_options, default="All", key="a_geo_val")
                if "All" not in selected_a_geo and selected_a_geo:
                    contacts_filtered = contacts_filtered[contacts_filtered[a_geo_col].isin(selected_a_geo)]
        
        with geo_col2:
            a_comp_mode = st.toggle("Compare Selected", key="a_comp_toggle")
        
        st.markdown(f"<small>Records: {len(contacts_filtered)} contacts</small>", unsafe_allow_html=True)
        
        if a_comp_mode and "All" not in selected_a_geo and len(selected_a_geo) == 2:
            cc1, cc2 = selected_a_geo[0], selected_a_geo[1]
            st.markdown(f"#### ⚔️ Attribution Comparison: {cc1} vs {cc2}")
            a_cols = st.columns(2)
            for i, val in enumerate([cc1, cc2]):
                df_loc = contacts_filtered[contacts_filtered[a_geo_col] == val]
                with a_cols[i]:
                    okr_scorecard(f"{val} Contacts", f"{len(df_loc):,}", color=accent)
                    if 'first_attribution' in df_loc.columns:
                        top_attr = df_loc['first_attribution'].value_counts().idxmax() if not df_loc.empty else "N/A"
                        okr_scorecard("Top Source", str(top_attr), color="#10b981")
            st.markdown("---")
        
        # === ATTRIBUTION INSIGHTS ===
        st.markdown("### **1. Attribution Analysis (First vs. Latest)**")
        
        if 'first_attribution' in contacts_filtered.columns and 'latest_attribution' in contacts_filtered.columns:
            f_counts = contacts_filtered['first_attribution'].value_counts().reset_index()
            f_counts.columns = ['Attribution', 'First']
            l_counts = contacts_filtered['latest_attribution'].value_counts().reset_index()
            l_counts.columns = ['Attribution', 'Latest']
            attr_df = pd.merge(f_counts, l_counts, on='Attribution', how='outer').fillna(0).head(15)
            
            # 1. Horizontal Stacked Bar Chart
            fig_attr = go.Figure()
            fig_attr.add_trace(go.Bar(
                y=attr_df['Attribution'], x=attr_df['First'],
                name='First Attribution', orientation='h',
                marker=dict(color='#0ea5e9')
            ))
            fig_attr.add_trace(go.Bar(
                y=attr_df['Attribution'], x=attr_df['Latest'],
                name='Latest Attribution', orientation='h',
                marker=dict(color='#10b981')
            ))
            fig_attr.update_layout(
                barmode='stack', height=450,
                title="Attribution Source Transition (First vs. Latest)",
                yaxis={'categoryorder':'total ascending'},
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Inter, sans-serif", color=text_color)
            )
            st.plotly_chart(fig_attr, use_container_width=True)
            
            # 2. Attribution Source Comparison Table
            st.markdown("#### **Attribution Detail Table**")
            st.dataframe(attr_df, use_container_width=True)
        
        st.markdown("---")
        
        # 3. Lead Source Summary
        st.markdown("### **2. Lead Source Summary**")
        ls_field = 'source' if 'source' in contacts_filtered.columns else None
        if ls_field:
            ls_summary = contacts_filtered.groupby(ls_field).size().reset_index(name='Count').sort_values('Count', ascending=False).head(15)
            st.dataframe(ls_summary, use_container_width=True)

# === TAB 6: CONSULTANT CAPACITY ===
with tab6:
    st.header("👨‍🏫 Consultant Capacity")
    consultants_today = consultant_data['consultants_today']
    consultants_weekly = consultant_data['consultants_weekly']
    
    # 1. Capacity Overviews (Pulse Grid)
    def detect_capacity_cols(df):
        name_col = [c for c in df.columns if 'name' in c.lower() or 'consultant' in c.lower()]
        appt_col = [c for c in df.columns if 'appointment' in c.lower() or 'total' in c.lower() or 'appt' in c.lower()]
        return (name_col[0] if name_col else None, appt_col[0] if appt_col else None)

    c_today_name, c_today_appt = detect_capacity_cols(consultants_today)
    c_weekly_name, c_weekly_appt = detect_capacity_cols(consultants_weekly)

    t_sum = int(consultants_today[c_today_appt].sum()) if not consultants_today.empty and c_today_appt else 0
    w_sum = int(consultants_weekly[c_weekly_appt].sum()) if not consultants_weekly.empty and c_weekly_appt else 0
    
    st.markdown(f"""
    <div style='text-align: center; margin-bottom: 2rem;'>
        <div style='display: inline-block; padding: 20px 40px; background: rgba(16,185,129,0.1); border: 1px solid #10b981; border-radius: 12px; box-shadow: 0 0 20px rgba(16,185,129,0.2);'>
            <span style='color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.1em;'>Today's Total Workforce</span>
            <h2 style='color: #10b981; margin: 10px 0 0; font-size: 2.5rem;'>{t_sum} Appointments</h2>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("📅 Today's Capacity")
        if not consultants_today.empty and c_today_name and c_today_appt:
            fig = px.bar(consultants_today, x=c_today_appt, y=c_today_name, title="Today's Appointments", 
                         labels={c_today_name: 'Consultant', c_today_appt: 'Appointments'}, 
                         color=c_today_appt, color_continuous_scale='Blues', orientation='h')
            fig.update_layout(height=400, yaxis_tickangle=0, paper_bgcolor=chart_bg, plot_bgcolor=chart_bg, font=dict(family="Helvetica", color=text_color))
            st.plotly_chart(fig, use_container_width=True)
    
    with col_chart2:
        st.subheader("📆 Weekly Capacity")
        if not consultants_weekly.empty and c_weekly_name and c_weekly_appt:
            fig = px.bar(consultants_weekly, x=c_weekly_appt, y=c_weekly_name, title="Weekly Appointments", 
                         labels={c_weekly_name: 'Consultant', c_weekly_appt: 'Appointments'}, 
                         color=c_weekly_appt, color_continuous_scale='Greens', orientation='h')
            fig.update_layout(height=400, yaxis_tickangle=0, paper_bgcolor=chart_bg, plot_bgcolor=chart_bg, font=dict(family="Helvetica", color=text_color))
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    d_col1, d_col2 = st.columns(2)
    with d_col1:
        st.markdown("#### **Today's Leaderboard**")
        if not consultants_today.empty:
            st.dataframe(consultants_today, use_container_width=True)
    with d_col2:
        st.markdown("#### **Weekly Leaderboard**")
        if not consultants_weekly.empty:
            st.dataframe(consultants_weekly, use_container_width=True)

#streamlit run "c:\Users\Hafsa Saleh\IdeaProjects\Themigration\ghl integration\mktdashboard.py"
