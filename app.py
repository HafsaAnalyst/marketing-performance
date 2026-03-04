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
        # return_exceptions=True prevents one failing service from crashing the whole sync
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    try:
        results = loop.run_until_complete(fetch_everything())
        
        # Process results and log any errors
        processed = []
        services = ["GHL", "Meta", "GA4", "Search Console"]
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                st.warning(f"⚠️ {services[i]} Sync limited: {str(res)}")
                processed.append({}) # Provide empty dict for failed service
            else:
                processed.append(res)
                
        # Merge GHL data if raw results exist
        ghl_raw = processed[0]
        if ghl_raw and isinstance(ghl_raw, dict) and "opportunities" in ghl_raw:
            from ghl_async_client import merge_contact_data, merge_opportunity_data
            ghl_raw["contacts"] = merge_contact_data(
                ghl_raw["contacts"], ghl_raw["opportunities"], 
                ghl_raw["appointments"], ghl_raw["pipelines"], ghl_raw["users"]
            )
            ghl_raw["opportunities"] = merge_opportunity_data(
                ghl_raw["opportunities"], ghl_raw["pipelines"], ghl_raw["users"]
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
    "🔍 SEO Performance", "💼 Pipeline Analysis", "👥 Attribution Analysis", "👨‍🏫 Consultant Capacity"
])

STAGE_ORDER = ["New Lead", "Qualifier", "Pre Sales (1)", "Pre Sales (2)", "Appointment Booked", "Won"]

# --- GHL DATA PROCESSING ---
ghl = all_data["ghl"]
opps = pd.DataFrame(ghl.get('opportunities', []))
contacts = pd.DataFrame(ghl.get('contacts', []))
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
    meta = all_data.get("meta", {})
    df_agg_raw = pd.DataFrame(meta.get("campaigns", []))
    df_daily_raw = pd.DataFrame(meta.get("daily", []))
    
    if not df_agg_raw.empty:
        # --- TOP CONTROL BAR ---
        all_meta_countries = sorted(df_agg_raw['Country'].unique())
        ctrl_c1, ctrl_c2 = st.columns([3, 1])
        with ctrl_c1:
            selected_meta_countries = st.multiselect("Filter by Country", all_meta_countries, default=all_meta_countries[:3] if len(all_meta_countries) > 3 else all_meta_countries, key="meta_country_filt")
        with ctrl_c2:
            meta_comparison_mode = st.toggle("Side-by-Side Comparison", key="meta_comp_toggle")

        df_agg_filt = df_agg_raw[df_agg_raw['Country'].isin(selected_meta_countries)].copy() if selected_meta_countries else df_agg_raw.copy()
        
        # 1. Performance KPIs
        st.markdown("### **1. Performance KPIs**")
        total_spend = df_agg_filt['Amount spent'].sum()
        total_leads = df_agg_filt['Results'].sum()
        avg_cpl = total_spend / total_leads if total_leads > 0 else 0
        total_links = df_agg_filt['Link clicks'].sum()
        total_outbound = df_agg_filt['Outbound clicks'].sum()
        total_impr_sum = df_agg_filt['Impressions'].sum()
        avg_ctr_link = df_agg_filt['CTR (link click-through rate)'].mean()
        avg_ctr_out = (total_outbound / total_impr_sum * 100) if total_impr_sum > 0 else 0
        
        k1, k2, k3 = st.columns(3)
        with k1: okr_scorecard("Total Spend", f"${total_spend:,.0f}")
        with k2: okr_scorecard("Total Leads", f"{int(total_leads):,}")
        with k3: okr_scorecard("Avg. CPL", f"${avg_cpl:.2f}")
        
        k4, k5, k6 = st.columns(3)
        with k4: okr_scorecard("Link Clicks", f"{int(total_links):,}")
        with k5: okr_scorecard("Outbound CTR", f"{avg_ctr_out:.2f}%", color="#10b981")
        with k6: okr_scorecard("Link CTR", f"{avg_ctr_link:.2f}%")

        st.divider()

        # 2. Creative Engagement (Hook & Hold)
        st.markdown("### **2. Creative Engagement (Hook & Hold)**")
        total_impr = df_agg_filt['Impressions'].sum()
        hook_rate = (df_agg_filt['3s Hold'].sum() / total_impr * 100) if total_impr > 0 else 0
        hold_rate = (df_agg_filt['Thruplays'].sum() / total_impr * 100) if total_impr > 0 else 0
        vh1, vh2 = st.columns(2)
        with vh1: okr_scorecard("Hook Rate (3s/Impr)", f"{hook_rate:.1f}%")
        with vh2: okr_scorecard("Hold Rate (Thru/Impr)", f"{hold_rate:.1f}%")

        st.divider()

        # 3. Video Retention Pipeline
        st.markdown("### **3. Video Retention Pipeline**")
        v_metrics = ['3s Hold', '50% Hook', '95% Hook', 'Thruplays']
        v_counts = [df_agg_filt[m].sum() for m in v_metrics]
        fig_hook = px.bar(x=v_counts, y=v_metrics, orientation='h', title="General Retention Pipeline (Total Views)")
        st.plotly_chart(apply_chart_style(fig_hook), use_container_width=True)

        st.divider()

        # 4. Campaign Performance Analysis
        col4_a, col4_b = st.columns(2)
        with col4_a:
            st.markdown("### **4. Campaign Performance Analysis**")
            fatigue_df = df_agg_filt.copy()
            fatigue_df = fatigue_df[pd.to_numeric(fatigue_df['Frequency'], errors='coerce') > 0]
            if not fatigue_df.empty:
                fig_fatigue = px.scatter(fatigue_df, x="Frequency", y="CTR (link click-through rate)", 
                                         size="Amount spent", color="Campaign", hover_name="Campaign",
                                         trendline="ols", trendline_color_override="red",
                                         title="CTR% vs. Frequency Fatigue")
                st.plotly_chart(apply_chart_style(fig_fatigue), use_container_width=True)
            else: st.info("No frequency data.")
        
        with col4_b:
            st.markdown("### **5. Strategic Performance Correlation**")
            df_agg_filt['Result Rate (%)'] = (df_agg_filt['Results'] / df_agg_filt['Impressions'] * 100).fillna(0)
            fig_strategic = px.scatter(df_agg_filt, x="CTR (link click-through rate)", y="Result Rate (%)",
                                       size="Results", color="Campaign", hover_name="Campaign",
                                       title="Messaging Relevance vs. Conversion Intent")
            st.plotly_chart(apply_chart_style(fig_strategic), use_container_width=True)

        st.divider()

        # 6. Engagement-to-Conversion Decay
        st.markdown("### **6. Engagement-to-Conversion Decay**")
        if not df_daily_raw.empty:
            df_d_filt = df_daily_raw.copy()
            df_d_filt['Date_DT'] = pd.to_datetime(df_d_filt['Date'])
            if len(df_d_filt) > 14:
                min_d = df_d_filt['Date_DT'].min()
                c1_d = df_d_filt[df_d_filt['Date_DT'] < min_d + timedelta(days=7)]
                c2_d = df_d_filt[df_d_filt['Date_DT'] > min_d + timedelta(days=14)]
                rr1, rr2 = c1_d['Result Rate Raw'].mean()*100, c2_d['Result Rate Raw'].mean()*100
                d_col1, d_col2 = st.columns(2)
                with d_col1: okr_scorecard("Result Rate (D1-7)", f"{rr1:.2f}%")
                with d_col2: okr_scorecard("Result Rate (D14-21)", f"{rr2:.2f}%", delta=f"{rr2-rr1:.2f}%" if rr1>0 else None)
            else: st.info("Min 14 days required for decay analysis.")

        st.divider()

        # 7. Landing Page Health
        st.markdown("### **7. Landing Page Health**")
        total_lp = df_agg_filt['Landing page views'].sum()
        drop_off = (1 - total_lp / total_links) * 100 if total_links > 0 else 0
        lph_col1, lph_col2 = st.columns([1, 2])
        with lph_col1:
            okr_scorecard("Drop-off Rate", f"{drop_off:.1f}%", color="#ef4444" if drop_off > 60 else "#10b981")
        with lph_col2:
            if drop_off > 60: st.warning("⚠️ High drop-off rate detected. Check page speed or relevancy.")
            else: st.success("✅ Healthy landing page engagement.")

        st.divider()

        # 8 & 9. Breakdown & Campaigns
        st.markdown("### **8. Conversion Type Breakdown**")
        with st.expander("🔍 View All Conversion Actions", expanded=False):
            all_actions = {}
            for map_data in df_agg_filt['_actions']:
                for k, v in map_data.items(): all_actions[k] = all_actions.get(k, 0) + v
            if all_actions:
                df_action = pd.DataFrame(list(all_actions.items()), columns=['Conversion Type', 'Count']).sort_values('Count', ascending=False)
                st.dataframe(df_action, use_container_width=True, hide_index=True)
            else: st.info("No conversion type data.")

        st.markdown("### **9. Meta Campaigns**")
        with st.expander("📂 View Detailed Campaigns", expanded=True):
            st.dataframe(df_agg_filt.drop(columns=['_actions']), use_container_width=True)
            st.download_button("📥 Download Report", df_agg_filt.to_csv(index=False).encode('utf-8'), "meta_report.csv")
    else:
        st.info("No Meta Ads campaign data found.")

# --- TAB 2: TRAFFIC BEHAVIOUR ---
with tabs[2]:
    ga4 = all_data.get("ga4", {})
    if ga4 and isinstance(ga4, dict) and "daily" in ga4:
        df_daily = pd.DataFrame(ga4["daily"])
        
        # 1. Engagement Overview
        st.markdown("### **1. Engagement Overview**")
        t_active = df_daily["Active Users"].sum()
        t_sessions = df_daily["Sessions"].sum()
        t_views = df_daily["Views"].sum()
        t_events = df_daily["Key Events"].sum()
        a_bounce = df_daily["Bounce Rate"].mean()
        
        k_cols = st.columns(5)
        with k_cols[0]: okr_scorecard("Active Users", f"{t_active:,}")
        with k_cols[1]: okr_scorecard("Sessions", f"{t_sessions:,}")
        with k_cols[2]: okr_scorecard("Views", f"{t_views:,}")
        with k_cols[3]: okr_scorecard("Key Events", f"{t_events:,}", color="#10b981")
        with k_cols[4]: okr_scorecard("Bounce Rate", f"{a_bounce:.1f}%", color="#ef4444")

        st.markdown("#### **User Engagement Trend**")
        df_daily['Date'] = pd.to_datetime(df_daily['Date'])
        df_daily_grp = df_daily.groupby('Date').sum().reset_index().sort_values('Date')
        fig_trend = px.area(df_daily_grp, x='Date', y=['Active Users', 'Sessions'], 
                             title="Engagement Trend", color_discrete_sequence=[accent, "#8b5cfc"])
        st.plotly_chart(apply_chart_style(fig_trend), use_container_width=True)

        st.divider()
        
        # 2. User Acquisition: Channel Trends
        st.markdown("### **2. User Acquisition: Channel Trends**")
        if "channels" in ga4:
            df_chan = pd.DataFrame(ga4["channels"])
            df_c_grp = df_chan.groupby('channel')['sessions'].sum().reset_index().sort_values('sessions', ascending=False)
            fig_chan = px.bar(df_c_grp, x="sessions", y="channel", orientation='h', title="Sessions by Channel Group", color="sessions")
            st.plotly_chart(apply_chart_style(fig_chan), use_container_width=True)

        st.divider()

        # 3. Traffic by Country
        st.markdown("### **3. Traffic by Country**")
        if "countries" in ga4:
            df_geo = pd.DataFrame(ga4["countries"])
            df_g = df_geo.sort_values("users", ascending=False).head(10)
            fig_geo = px.pie(df_g, values="users", names="country", hole=0.4, title="User Distribution by Country")
            st.plotly_chart(apply_chart_style(fig_geo), use_container_width=True)

        st.divider()

        # 4. Key Events Behaviour
        st.markdown("### **4. Key Events Behaviour**")
        if "events" in ga4:
            df_events = pd.DataFrame(ga4["events"])
            df_e_grp = df_events.groupby('event')['count'].sum().reset_index().sort_values('count', ascending=False).head(15)
            fig_events = px.bar(df_e_grp, x="count", y="event", orientation='h', title="Key Events Breakdown", color="count")
            st.plotly_chart(apply_chart_style(fig_events), use_container_width=True)

        st.divider()

        # 5. Page Performance Analysis
        st.markdown("### **5. Page Performance Analysis**")
        if "topPages" in ga4:
            df_pages = pd.DataFrame(ga4["topPages"])
            if not df_pages.empty and 'page' in df_pages.columns:
                df_pages_sorted = df_pages.sort_values('sessions', ascending=False).head(20)
                fig_pages_ga = px.bar(
                    df_pages_sorted, x="sessions", y="page", orientation='h',
                    title="Top Landing Pages by Sessions", color="sessions",
                    color_continuous_scale="Blues"
                )
                st.plotly_chart(apply_chart_style(fig_pages_ga), use_container_width=True)
                st.dataframe(df_pages_sorted[['page','sessions','users','conversions']].rename(columns={
                    'page': 'Landing Page', 'sessions': 'Sessions', 'users': 'Users', 'conversions': 'Key Events'
                }), use_container_width=True, hide_index=True)
            else:
                st.info("No page data available.")
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

        all_gsc_countries = sorted(df_trend_raw['Country_Code'].unique()) if 'Country_Code' in df_trend_raw.columns else []
        selected_gsc_countries = st.multiselect("Filter by Country", all_gsc_countries, default=all_gsc_countries[:5] if len(all_gsc_countries) > 5 else all_gsc_countries, key="gsc_country_filt")
        
        df_t_filt = df_trend_raw[df_trend_raw['Country_Code'].isin(selected_gsc_countries)].copy() if selected_gsc_countries else df_trend_raw.copy()
        df_t_grp = df_t_filt.groupby('Date').agg({'clicks': 'sum', 'impressions': 'sum', 'ctr': 'mean', 'position': 'mean'}).reset_index().sort_values('Date')

        # 1. Performance KPIs
        st.markdown("### **1. Performance KPI's**")
        total_clicks = df_t_grp['clicks'].sum()
        total_impr = df_t_grp['impressions'].sum()
        avg_ctr = (total_clicks / total_impr * 100) if total_impr > 0 else 0
        avg_pos = df_t_grp['position'].mean()
        
        k_cols = st.columns(4)
        with k_cols[0]: okr_scorecard("Total Clicks", f"{total_clicks:,}")
        with k_cols[1]: okr_scorecard("Impressions", f"{total_impr:,}")
        with k_cols[2]: okr_scorecard("Avg. CTR", f"{avg_ctr:.2f}%")
        with k_cols[3]: okr_scorecard("Avg. Position", f"{avg_pos:.1f}", color="#8b5cfc")

        st.divider()

        # 2. Performance Trend
        st.markdown("### **2. Performance**")
        fig_p = go.Figure()
        fig_p.add_trace(go.Scatter(x=df_t_grp['Date'], y=df_t_grp['clicks'], name="Clicks", line=dict(color=accent, width=3), fill='tozeroy'))
        fig_p.add_trace(go.Scatter(x=df_t_grp['Date'], y=df_t_grp['impressions'], name="Impressions", yaxis="y2", line=dict(color="#8b5cfc", width=2, dash='dot')))
        fig_p.update_layout(
            yaxis2=dict(title="Impressions", overlaying="y", side="right", showgrid=False),
            hovermode="x unified", title="Search Console Volume Trend"
        )
        st.plotly_chart(apply_chart_style(fig_p), use_container_width=True)

        st.divider()

        # 3. Golden Opportunity Matrix — Keyword Rankings
        st.markdown("### **3. Golden Opportunity Matrix — Keyword Rankings**")
        df_q_grp = pd.DataFrame()
        if not df_query_raw.empty and 'Query' in df_query_raw.columns:
            df_q_filt = df_query_raw[df_query_raw['Country_Code'].isin(selected_gsc_countries)] if selected_gsc_countries else df_query_raw
            df_q_grp = df_q_filt.groupby('Query').agg({'clicks':'sum', 'impressions':'sum', 'position':'mean'}).reset_index()
            if not df_q_grp.empty:
                df_q_grp['CTR'] = (df_q_grp['clicks'] / df_q_grp['impressions'] * 100).fillna(0)
                plot_df = df_q_grp[df_q_grp['clicks'] > 0].copy()
                if not plot_df.empty:
                    fig_mat = px.scatter(plot_df, x="position", y="impressions", size="clicks", color="CTR",
                                         hover_name="Query", log_y=True, title="Strategic Visibility vs. Rank")
                    fig_mat.add_vline(x=10, line_dash="dash", line_color="rgba(255,100,100,0.5)", annotation_text="Page 2")
                    st.plotly_chart(apply_chart_style(fig_mat), use_container_width=True)
        else:
            st.info("No keyword query data available.")

        st.divider()

        # 4. Content Performance — Clicks vs CTR
        st.markdown("### **4. Content Performance — Clicks vs CTR**")
        if not df_pages_raw.empty and 'Page' in df_pages_raw.columns:
            df_p_filt = df_pages_raw[df_pages_raw['Country_Code'].isin(selected_gsc_countries)] if selected_gsc_countries else df_pages_raw
            df_p_grp = df_p_filt.groupby('Page').agg({'clicks':'sum', 'ctr':'mean'}).reset_index().sort_values('clicks', ascending=False).head(15)
            fig_pages_seo = px.bar(df_p_grp, x="clicks", y="Page", orientation='h', color="clicks", title="Top Pages by Clicks")
            st.plotly_chart(apply_chart_style(fig_pages_seo), use_container_width=True)
        else:
            st.info("No page performance data available.")

        st.divider()

        # 5. Search Console Keyword Intelligence
        st.markdown("### **5. Search Console Keyword Intelligence**")
        if not df_q_grp.empty:
            st.dataframe(df_q_grp.sort_values('clicks', ascending=False).head(100), use_container_width=True, hide_index=True)
        else:
            st.info("No keyword data to display.")
    else:
        st.warning("⚠️ SEO Sync limited: 403 User does not have sufficient permission.")
        st.info("💡 **Resolution:** Add `antigravity-fetcher@ghldataset.iam.gserviceaccount.com` as a 'Viewer' in Google Search Console → Settings → Users & Permissions for 'https://themigration.com.au/'.")


# --- TAB 4: PIPELINE ANALYSIS ---
with tabs[4]:
    if not opps.empty:
        # 1. Pipeline KPI's
        st.markdown("### **1. Pipeline KPI's**")
        total_val = opps['Opportunity Value'].sum() if 'Opportunity Value' in opps.columns else 0
        l2c_open_count = 0
        if 'Pipeline' in opps.columns and 'Status' in opps.columns:
            l2c_open_count = len(opps[(opps['Pipeline'] == 'L2C - Education') & (opps['Status'] == 'open')])

        k_cols = st.columns(3)
        with k_cols[0]: okr_scorecard("Total Opportunities", f"{len(opps):,}")
        with k_cols[1]: okr_scorecard("Pipeline Value", f"${total_val:,.0f}", color="#10b981")
        with k_cols[2]: okr_scorecard("L2C Education (Open)", f"{l2c_open_count:,}", color="#8b5cfc")
        
        st.divider()
        
        # 2. Opportunity Analysis
        st.markdown("### **2. Opportunity Analysis**")
        col_chart1, col_chart2 = st.columns(2)
        p_colors = {'won': '#10b981', 'open': '#1e3a8a', 'lost': '#94a3b8', 'abandoned': '#64748b'}
        
        with col_chart1:
            if 'Lead Owner' in opps.columns and 'Status' in opps.columns:
                owner_status = opps.groupby(['Lead Owner', 'Status']).size().reset_index(name='Count')
                fig_o = px.bar(owner_status, x='Count', y='Lead Owner', color='Status', orientation='h', 
                               color_discrete_map=p_colors, barmode='stack', title="Opporturnity owners by status")
                st.plotly_chart(apply_chart_style(fig_o), use_container_width=True)
        
        with col_chart2:
            if 'Status' in opps.columns:
                status_counts = opps['Status'].value_counts().reset_index()
                fig_s = px.pie(status_counts, values='count', names='Status', hole=0.6, title="Donut chart by status",
                               color='Status', color_discrete_map=p_colors)
                fig_s.add_annotation(text=f"<b>{len(opps):,}</b><br>Total", showarrow=False, font_size=20)
                st.plotly_chart(apply_chart_style(fig_s), use_container_width=True)
        
        st.divider()
        
        # 3. Phase-Based Pipeline Funnel
        st.markdown("### **3. Phase-Based Pipeline Funnel (L2C Education)**")
        if 'Pipeline' in opps.columns and 'Status' in opps.columns:
            l2c_df = opps[opps['Pipeline'] == 'L2C - Education'].copy()
            if not l2c_df.empty:
                funnel_data = []
                # Ensure STAGE_ORDER includes 'Won' for the funnel
                S_ORDER = ["New Lead", "Qualifier", "Pre Sales (1)", "Pre Sales (2)", "Appointment Booked", "Won"]
                if 'Stage' in l2c_df.columns:
                    for stage in S_ORDER[:-1]:
                        count = len(l2c_df[(l2c_df['Stage'] == stage) & (l2c_df['Status'] == 'open')])
                        funnel_data.append({'Stage': stage, 'Count': count})
                    funnel_data.append({'Stage': 'Won', 'Count': len(l2c_df[l2c_df['Status'] == 'won'])})
                
                if funnel_data:
                    f_df = pd.DataFrame(funnel_data)
                    fig_f = px.bar(f_df, x="Count", y="Stage", orientation='h', title="Intent Pipeline Funnel",
                                   color="Count", color_continuous_scale="Viridis")
                    st.plotly_chart(apply_chart_style(fig_f), use_container_width=True)

        st.divider()
        
        # 4. Lead Source Analysis
        st.markdown("### **4. Lead Source Analysis**")
        if 'Lead Source' in opps.columns:
            ls_grp = opps.groupby(['Lead Source', 'Status']).size().reset_index(name='Count')
            fig_ls = px.bar(ls_grp, x='Count', y='Lead Source', color='Status', orientation='h', 
                             color_discrete_map=p_colors, title="Lead Source Breakdown")
            st.plotly_chart(apply_chart_style(fig_ls), use_container_width=True)

        st.divider()
        # 5. Opportunity Pipeline Bubble Chart
        st.markdown("### **5. Opportunity Pipeline Bubble Chart**")
        if 'Lead Owner' in opps.columns and 'Opportunity Value' in opps.columns:
            bubble_df = opps.groupby('Lead Owner').agg({'Opportunity Value':'sum', 'created_date':'count'}).reset_index()
            bubble_df.columns = ['Lead Owner', 'Value', 'Count']
            fig_b = px.scatter(bubble_df, x="Count", y="Value", size="Value", color="Lead Owner", hover_name="Lead Owner", title="Owner Impact Matrix")
            st.plotly_chart(apply_chart_style(fig_b), use_container_width=True)
    else:
        st.info("No opportunity data found.")

# --- TAB 5: ATTRIBUTION ANALYSIS ---
with tabs[5]:
    if not contacts.empty:
        st.markdown("### **1. Attribution Analysis (First vs. Latest)**")
        if 'first_attribution' in contacts.columns and 'latest_attribution' in contacts.columns:
            # Aggregate First vs latest
            f_counts = contacts['first_attribution'].value_counts().reset_index().head(15)
            f_counts.columns = ['Source', 'First']
            l_counts = contacts['latest_attribution'].value_counts().reset_index().head(15)
            l_counts.columns = ['Source', 'Latest']
            attr_df = pd.merge(f_counts, l_counts, on='Source', how='outer').fillna(0)
            
            fig_attr = go.Figure()
            fig_attr.add_trace(go.Bar(y=attr_df['Source'], x=attr_df['First'], name='First Attrib', orientation='h', marker=dict(color='#0ea5e9')))
            fig_attr.add_trace(go.Bar(y=attr_df['Source'], x=attr_df['Latest'], name='Latest Attrib', orientation='h', marker=dict(color='#10b981')))
            fig_attr.update_layout(barmode='stack', title="Attribution Source Transition", yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(apply_chart_style(fig_attr), use_container_width=True)
            
            st.markdown("#### **Attribution Detail Table**")
            st.dataframe(attr_df, use_container_width=True, hide_index=True)

            st.markdown("#### **First Attribution Distribution**")
            fig_pie = px.pie(attr_df, values='First', names='Source', hole=0.5, title="First Attribution Breakdown")
            st.plotly_chart(apply_chart_style(fig_pie), use_container_width=True)
        
        st.divider()
        st.markdown("### **2. Lead Source Summary**")
        if 'source' in contacts.columns:
            ls_sum = contacts['source'].value_counts().reset_index().head(20)
            st.dataframe(ls_sum, use_container_width=True, hide_index=True)
    else:
        st.info("No contact data found.")

# --- TAB 6: CONSULTANT CAPACITY ---
with tabs[6]:
    st.markdown("### **👨‍🏫 Consultant Pulse Leaderboard**")
    
    # Scorecards
    df_t = pd.DataFrame(consultant_today)
    df_w = pd.DataFrame(consultant_weekly)
    
    t_appts = int(df_t['total_appointments'].sum()) if not df_t.empty else 0
    w_appts = int(df_w['total_appointments'].sum()) if not df_w.empty else 0
    t_rev = float(df_t['total_value'].sum()) if not df_t.empty else 0
    
    s1, s2, s3 = st.columns(3)
    with s1: okr_scorecard("Today's Appointments", f"{t_appts}")
    with s2: okr_scorecard("Weekly Appointments", f"{w_appts}", color="#10b981")
    with s3: okr_scorecard("Today's Revenue Impact", f"${t_rev:,.0f}", color="#8b5cfc")

    st.divider()
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### **📅 Today's Capacity**")
        if not df_t.empty:
            fig_t = px.bar(df_t.sort_values('total_appointments'), x="total_appointments", y="consultant_name", 
                           orientation='h', title="Appointments per Consultant (Today)", color="total_appointments", color_continuous_scale="Blues")
            st.plotly_chart(apply_chart_style(fig_t), use_container_width=True)
    
    with c2:
        st.markdown("#### **📆 Weekly Capacity**")
        if not df_w.empty:
            fig_w = px.bar(df_w.sort_values('total_appointments'), x="total_appointments", y="consultant_name", 
                           orientation='h', title="Appointments per Consultant (Weekly)", color="total_appointments", color_continuous_scale="Greens")
            st.plotly_chart(apply_chart_style(fig_w), use_container_width=True)

    st.divider()
    
    l1, l2 = st.columns(2)
    with l1:
        st.markdown("#### **Today's Leaderboard**")
        if not df_t.empty:
            cols = ['consultant_name', 'total_appointments', 'won_count', 'total_value']
            st.dataframe(df_t[cols].sort_values('total_value', ascending=False), use_container_width=True, hide_index=True)
    
    with l2:
        st.markdown("#### **Weekly Leaderboard**")
        if not df_w.empty:
            cols = ['consultant_name', 'total_appointments', 'won_count', 'total_value']
            st.dataframe(df_w[cols].sort_values('total_value', ascending=False), use_container_width=True, hide_index=True)
