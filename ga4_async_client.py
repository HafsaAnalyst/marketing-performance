"""
Async GA4 (Google Analytics 4) API Client - High-performance data fetching
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest, FilterExpression
)

import streamlit as st
import json
from google.oauth2 import service_account

# ==================== CONFIGURATION ====================
try:
    PROPERTY_ID = st.secrets["google"]["property_id"]
except:
    PROPERTY_ID = "354763938"

def get_google_creds():
    """Helper to get credentials from st.secrets or local file"""
    scopes = [
        'https://www.googleapis.com/auth/analytics.readonly',
        'https://www.googleapis.com/auth/webmasters.readonly'
    ]
    try:
        if "google" in st.secrets and "gsc_credentials" in st.secrets["google"]:
            secret = st.secrets["google"]["gsc_credentials"]
            if isinstance(secret, str):
                return service_account.Credentials.from_service_account_info(json.loads(secret), scopes=scopes)
            return service_account.Credentials.from_service_account_info(dict(secret), scopes=scopes)
    except:
        pass
    
    if os.path.exists("service_account.json"):
        return service_account.Credentials.from_service_account_file("service_account.json", scopes=scopes)
    return None


class GA4AsyncClient:
    """Async GA4 API Client"""
    
    def __init__(self):
        self._client: Optional[BetaAnalyticsDataClient] = None
        self._data_cache: Optional[Dict] = None
        self._last_fetch: Optional[datetime] = None
    
    def get_client(self) -> BetaAnalyticsDataClient:
        """Get GA4 client with manual credentials injection"""
        if self._client is None:
            creds = get_google_creds()
            if creds:
                self._client = BetaAnalyticsDataClient(credentials=creds)
            else:
                self._client = BetaAnalyticsDataClient()
        return self._client
    
    async def fetch_traffic_summary(self, start_date: str, end_date: str) -> Dict:
        """Fetch main traffic metrics"""
        client = self.get_client()
        
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
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
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        )
        
        response = client.run_report(request)
        
        # Aggregate totals
        total_active_users = 0
        total_sessions = 0
        total_duration = 0
        total_bounce = 0
        total_new_users = 0
        total_users = 0
        total_pageviews = 0
        total_conversions = 0
        row_count = 0
        
        for row in response.rows:
            total_active_users += int(row.metric_values[0].value)
            total_sessions += int(row.metric_values[1].value)
            total_duration += float(row.metric_values[2].value)
            total_bounce += float(row.metric_values[3].value)
            total_new_users += int(row.metric_values[4].value)
            total_users += int(row.metric_values[5].value)
            total_pageviews += int(row.metric_values[6].value)
            total_conversions += int(row.metric_values[7].value)
            row_count += 1
        
        if row_count > 0:
            return {
                'activeUsers': total_active_users,
                'sessions': total_sessions,
                'avgSessionDuration': total_duration / row_count,
                'bounceRate': (total_bounce / row_count) * 100,
                'newUsers': total_new_users,
                'totalUsers': total_users,
                'pageViews': total_pageviews,
                'conversions': total_conversions
            }
        
        return {
            'activeUsers': 0, 'sessions': 0, 'avgSessionDuration': 0,
            'bounceRate': 0, 'newUsers': 0, 'totalUsers': 0,
            'pageViews': 0, 'conversions': 0
        }
    
    async def fetch_channels(self, start_date: str, end_date: str, limit: int = 20) -> List[Dict]:
        """Fetch traffic by channel"""
        client = self.get_client()
        
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions"), Metric(name="activeUsers"), Metric(name="keyEvents")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            limit=limit
        )
        
        response = client.run_report(request)
        
        data = []
        for row in response.rows:
            data.append({
                'channel': row.dimension_values[0].value,
                'sessions': int(row.metric_values[0].value),
                'activeUsers': int(row.metric_values[1].value),
                'conversions': int(row.metric_values[2].value)
            })
        
        return data
    
    async def fetch_top_pages(self, start_date: str, end_date: str, limit: int = 20) -> List[Dict]:
        """Fetch top landing pages"""
        client = self.get_client()
        
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name="landingPage")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="activeUsers"),
                Metric(name="averageSessionDuration"),
                Metric(name="keyEvents")
            ],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            limit=limit
        )
        
        response = client.run_report(request)
        
        data = []
        for row in response.rows:
            data.append({
                'page': row.dimension_values[0].value,
                'sessions': int(row.metric_values[0].value),
                'users': int(row.metric_values[1].value),
                'avgDuration': float(row.metric_values[2].value),
                'conversions': int(row.metric_values[3].value)
            })
        
        return data
    
    async def fetch_events(self, start_date: str, end_date: str, limit: int = 20) -> List[Dict]:
        """Fetch top events"""
        client = self.get_client()
        
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount"), Metric(name="totalUsers")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            limit=limit
        )
        
        response = client.run_report(request)
        
        data = []
        for row in response.rows:
            users = int(row.metric_values[1].value)
            data.append({
                'event': row.dimension_values[0].value,
                'count': int(row.metric_values[0].value),
                'users': users,
                'countPerUser': round(int(row.metric_values[0].value) / users, 2) if users > 0 else 0
            })
        
        return data
    
    async def fetch_countries(self, start_date: str, end_date: str, limit: int = 20) -> List[Dict]:
        """Fetch users by country"""
        client = self.get_client()
        
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name="country")],
            metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            limit=limit
        )
        
        response = client.run_report(request)
        
        data = []
        for row in response.rows:
            data.append({
                'country': row.dimension_values[0].value,
                'users': int(row.metric_values[0].value),
                'sessions': int(row.metric_values[1].value)
            })
        
        return data
    
    async def fetch_all_data(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Fetch all GA4 data concurrently"""
        # Run all requests concurrently
        traffic, channels, pages, events, countries = await asyncio.gather(
            self.fetch_traffic_summary(start_date, end_date),
            self.fetch_channels(start_date, end_date),
            self.fetch_top_pages(start_date, end_date),
            self.fetch_events(start_date, end_date),
            self.fetch_countries(start_date, end_date)
        )
        
        return {
            'traffic': traffic,
            'channels': channels,
            'topPages': pages,
            'events': events,
            'countries': countries,
            'fetched_at': datetime.now().isoformat()
        }
    
    def invalidate_cache(self):
        """Clear cache (for future use)"""
        self._data_cache = None
        self._last_fetch = None


# Global instance
ga4_client = GA4AsyncClient()


async def fetch_ga4_data(start_date: str, end_date: str) -> Dict[str, Any]:
    """Fetch all GA4 data"""
    return await ga4_client.fetch_all_data(start_date, end_date)


if __name__ == "__main__":
    async def test():
        result = await fetch_ga4_data('2025-11-01', '2026-02-28')
        print(f"Traffic: {result['traffic']}")
        print(f"Channels: {len(result['channels'])}")
        print(f"Top Pages: {len(result['topPages'])}")
        print(f"Events: {len(result['events'])}")
    
    asyncio.run(test())
