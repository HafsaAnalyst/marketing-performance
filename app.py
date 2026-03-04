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
        try:
            auth_user = st.secrets["auth"]["username"]
            auth_pass = st.secrets["auth"]["password"]
        except:
            st.error("Missing Secrets: Please configure `auth.username` and `auth.password` in Streamlit Secrets.")
            st.stop()
            
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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def fetch_everything():
        # Fetching tasks
        tasks = [
            ghl_client.fetch_all_data(),
            fetch_meta_data(start_str, end_str),
            fetch_ga4_data(start_str, end_str),
            fetch_gsc_data(start_str, end_str)
        ]
        return await asyncio.gather(*tasks)
    
    try:
        results = loop.run_until_complete(fetch_everything())
        return {"ghl": results[0], "meta": results[1], "ga4": results[2], "gsc": results[3]}
    except Exception as e:
        error_details = traceback.format_exc()
        st.error(f"Intelligence Sync Failed: {e}")
        with st.expander("Show Technical Details"):
            st.code(error_details)
        return None
    finally:
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

tabs = st.tabs([
    "🎯 Our Vision", "📊 Ads & Creatives", "📈 Traffic Behavior", 
    "🔍 SEO Performance", "💼 Pipeline Analysis", "👥 Attribution", "👨‍🏫 Consultants"
])

# --- GHL DATA PROCESSING ---
ghl = all_data["ghl"]
opps = pd.DataFrame(ghl.get('opportunities', []))
contacts = pd.DataFrame(ghl.get('contacts', []))
consultant_raw = ghl.get('consultants', [])

# Map GHL columns
if not opps.empty:
    mapping = {
        'value': 'Opportunity Value',
        'status': 'Status',
        'pipeline_name': 'Pipeline',
        'stage_name': 'Stage',
        'assigned_to': 'Lead Owner',
        'date_added': 'created_date'
    }
    # Safe rename logic
    if hasattr(opps, 'columns') and opps.columns is not None:
        safe_mapping = {k: v for k, v in mapping.items() if k in opps.columns}
        opps.rename(columns=safe_mapping, inplace=True)
        
        if 'created_date' in opps.columns:
            opps['created_date'] = pd.to_datetime(opps['created_date']).dt.date

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
    meta = all_data["meta"]
    meta_summary = meta.get("summary", {})
    campaigns = pd.DataFrame(meta.get("campaigns", []))
    
    if not campaigns.empty:
        st.subheader("Performance KPIs")
        k1, k2, k3 = st.columns(3)
        with k1: okr_scorecard("Total Spend", f"${meta_summary.get('total_spend', 0):,.0f}")
        with k2: okr_scorecard("Total Leads", f"{int(meta_summary.get('total_leads', 0)):,}")
        with k3: okr_scorecard("Avg. CPL", f"${meta_summary.get('cpl', 0):.2f}")
        
        st.write("---")
        
        # hook/hold metrics if available
        if '3s Hold' in campaigns.columns:
            st.subheader("Creative Engagement")
            k4, k5 = st.columns(2)
            total_impr = campaigns['impressions'].sum()
            hook_rate = (campaigns['3s Hold'].sum() / total_impr * 100) if total_impr > 0 else 0
            hold_rate = (campaigns['Thruplays'].sum() / total_impr * 100) if total_impr > 0 else 0
            with k4: okr_scorecard("Hook Rate (3s/Impr)", f"{hook_rate:.1f}%")
            with k5: okr_scorecard("Hold Rate (Thru/Impr)", f"{hold_rate:.1f}%")
        
        st.subheader("Campaign Breakdown")
        st.dataframe(campaigns, use_container_width=True)
    else:
        st.info("No Meta Ads data found.")

# --- TAB 2: TRAFFIC BEHAVIOR ---
with tabs[2]:
    ga4 = all_data["ga4"]
    traffic = ga4.get("traffic", {})
    channels = pd.DataFrame(ga4.get("channels", []))
    
    if traffic:
        st.subheader("Engagement Overview")
        k1, k2, k3, k4 = st.columns(4)
        with k1: okr_scorecard("Active Users", f"{traffic.get('activeUsers', 0):,}")
        with k2: okr_scorecard("Sessions", f"{traffic.get('sessions', 0):,}")
        with k3: okr_scorecard("Events", f"{traffic.get('conversions', 0):,}", color="#10b981")
        with k4: okr_scorecard("Bounce Rate", f"{traffic.get('bounceRate', 0):.1f}%", color="#ef4444")
        
        st.write("---")
        
        if not channels.empty:
            st.subheader("Acquisition Channels")
            fig = px.bar(channels, x="channel", y="sessions", color="channel", title="Sessions by Channel")
            st.plotly_chart(apply_chart_style(fig), use_container_width=True)
            
            st.subheader("Country Distribution")
            countries = pd.DataFrame(ga4.get("countries", []))
            if not countries.empty:
                fig_c = px.pie(countries.head(10), values="users", names="country", hole=0.4, title="Top 10 Countries")
                st.plotly_chart(apply_chart_style(fig_c), use_container_width=True)
    else:
        st.info("No GA4 data found.")

# --- TAB 3: SEO PERFORMANCE ---
with tabs[3]:
    gsc = all_data["gsc"]
    gsc_summary = gsc.get("summary", {})
    gsc_trend = pd.DataFrame(gsc.get("trend", []))
    gsc_queries = pd.DataFrame(gsc.get("queries", []))
    
    if gsc_summary:
        st.subheader("SEO Overview")
        k1, k2, k3, k4 = st.columns(4)
        with k1: okr_scorecard("Total Clicks", f"{gsc_summary.get('total_clicks', 0):,}")
        with k2: okr_scorecard("Impressions", f"{gsc_summary.get('total_impressions', 0):,}")
        with k3: okr_scorecard("Avg. CTR", f"{gsc_summary.get('avg_ctr', 0):.2f}%")
        with k4: okr_scorecard("Avg. Position", f"{gsc_summary.get('avg_position', 0):.1f}")
        
        if not gsc_trend.empty:
            st.subheader("Clicks & Impressions Trend")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=gsc_trend['date'], y=gsc_trend['clicks'], name="Clicks", line=dict(color=accent, width=3), fill='tozeroy'))
            fig.add_trace(go.Scatter(x=gsc_trend['date'], y=gsc_trend['impressions'], name="Impressions", line=dict(color="#8b5cfc", width=2, dash='dot'), yaxis="y2"))
            fig.update_layout(yaxis2=dict(overlaying='y', side='right'))
            st.plotly_chart(apply_chart_style(fig), use_container_width=True)
            
        if not gsc_queries.empty:
            st.subheader("Top Queries")
            st.dataframe(gsc_queries.head(20), use_container_width=True)
    else:
        st.info("No SEO data found.")

# --- TAB 4: PIPELINE ANALYSIS ---
with tabs[4]:
    if not opps.empty:
        st.subheader("Pipeline Analysis")
        o1, o2, o3 = st.columns(3)
        with o1: okr_scorecard("Total Opportunities", f"{len(opps):,}")
        with o2: okr_scorecard("Pipeline Value", f"${opps['Opportunity Value'].sum():,.0f}", color="#10b981")
        with o3:
            l2c_open = len(opps[(opps['Pipeline'] == 'L2C - Education') & (opps['Status'] == 'open')])
            okr_scorecard("Open L2C Opps", f"{l2c_open:,}", color="#8b5cfc")
            
        st.write("---")
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.subheader("Funnel Visualization")
            STAGE_ORDER = ["New Lead", "Qualifier", "Pre Sales (1)", "Pre Sales (2)", "Appointment Booked", "Won"]
            funnel_data = []
            for s in STAGE_ORDER:
                count = len(opps[(opps['Stage'] == s) & (opps['Status'] == 'open')]) if s != "Won" else len(opps[opps['Status'] == 'won'])
                funnel_data.append({"Stage": s, "Count": count})
            fig_f = px.funnel(pd.DataFrame(funnel_data), x="Count", y="Stage", color_discrete_sequence=[accent])
            st.plotly_chart(apply_chart_style(fig_f), use_container_width=True)
            
        with col_c2:
            st.subheader("Status Breakdown")
            status_df = opps['Status'].value_counts().reset_index()
            fig_p = px.pie(status_df, values='count', names='Status', hole=0.5, color_discrete_sequence=[accent, "#1e3a8a", "#94a3b8"])
            st.plotly_chart(apply_chart_style(fig_p), use_container_width=True)
    else:
        st.info("No opportunity data found.")

# --- TAB 5: ATTRIBUTION ---
with tabs[5]:
    if not contacts.empty:
        st.subheader("Attribution Analysis")
        if 'first_attribution' in contacts.columns and 'latest_attribution' in contacts.columns:
            f_counts = contacts['first_attribution'].value_counts().reset_index()
            f_counts.columns = ['Source', 'First']
            l_counts = contacts['latest_attribution'].value_counts().reset_index()
            l_counts.columns = ['Source', 'Latest']
            attr_df = pd.merge(f_counts, l_counts, on='Source', how='outer').fillna(0).head(15)
            
            fig = go.Figure()
            fig.add_trace(go.Bar(y=attr_df['Source'], x=attr_df['First'], name='First Attribution', orientation='h', marker=dict(color=accent)))
            fig.add_trace(go.Bar(y=attr_df['Source'], x=attr_df['Latest'], name='Latest Attribution', orientation='h', marker=dict(color="#8b5cfc")))
            fig.update_layout(barmode='stack', yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(apply_chart_style(fig), use_container_width=True)
            
            st.dataframe(attr_df, use_container_width=True)
    else:
        st.info("No contact attribution data found.")

# --- TAB 6: CONSULTANTS ---
with tabs[6]:
    st.subheader("Consultant Capacity")
    if consultant_raw:
        df_cons = pd.DataFrame(consultant_raw)
        total_appts = int(df_cons['total_appointments'].sum())
        
        st.markdown(f"""
        <div style='text-align: center; margin-bottom: 2rem;'>
            <div style='display: inline-block; padding: 20px 40px; background: rgba(45, 212, 191, 0.1); border: 1px solid {accent}; border-radius: 12px;'>
                <span style='color: {secondary_text}; font-size: 0.9rem; text-transform: uppercase;'>Today's Workforce Impact</span>
                <h2 style='color: {accent}; margin: 10px 0 0; font-size: 2.5rem;'>{total_appts} Appointments</h2>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(df_cons, x="total_appointments", y="consultant_name", orientation='h', title="Appointments per Consultant", color_discrete_sequence=[accent])
            st.plotly_chart(apply_chart_style(fig), use_container_width=True)
        with c2:
            fig_v = px.bar(df_cons, x="total_value", y="consultant_name", orientation='h', title="Revenue Impact per Consultant", color_discrete_sequence=["#8b5cfc"])
            st.plotly_chart(apply_chart_style(fig_v), use_container_width=True)
            
        st.markdown("#### Leaderboard")
        st.dataframe(df_cons[['consultant_name', 'total_appointments', 'won_count', 'total_value']].sort_values('total_value', ascending=False), use_container_width=True)
    else:
        st.info("No consultant data found.")

# streamlit run app.py
