"""
Async GSC (Google Search Console) API Client - High-performance data fetching
"""
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build

import streamlit as st
import json

# ==================== CONFIGURATION ====================
GSC_SITE_URL = "https://themigration.com.au/"

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


class GSCAsyncClient:
    """Async GSC API Client"""
    
    def __init__(self):
        self._service = None
        self._data_cache: Optional[Dict] = None
        self._last_fetch: Optional[datetime] = None
    
    def get_service(self):
        """Get GSC service with manual credentials injection"""
        if self._service is None:
            credentials = get_google_creds()
            if not credentials:
                raise Exception("Google credentials not found (checked st.secrets and service_account.json)")
            
            # Add required scope if not present
            scopes = getattr(credentials, 'scopes', []) or []
            if 'https://www.googleapis.com/auth/webmasters.readonly' not in scopes:
                credentials = credentials.with_scopes(['https://www.googleapis.com/auth/webmasters.readonly'])
                
            self._service = build('searchconsole', 'v1', credentials=credentials)
        return self._service
    
    async def fetch_trend(self, start_date: str, end_date: str) -> List[Dict]:
        """Fetch daily trend data"""
        service = self.get_service()
        
        request = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': ['date'],
            'rowLimit': 1000
        }
        
        response = service.searchanalytics().query(
            siteUrl=GSC_SITE_URL,
            body=request
        ).execute()
        
        rows = response.get('rows', [])
        data = []
        for row in rows:
            data.append({
                'date': row['keys'][0],
                'clicks': row['clicks'],
                'impressions': row['impressions'],
                'ctr': row['ctr'] * 100,  # Convert to percentage
                'position': row['position']
            })
        
        return data
    
    async def fetch_queries(self, start_date: str, end_date: str, limit: int = 50) -> List[Dict]:
        """Fetch top search queries"""
        service = self.get_service()
        
        request = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': ['query'],
            'rowLimit': limit
        }
        
        response = service.searchanalytics().query(
            siteUrl=GSC_SITE_URL,
            body=request
        ).execute()
        
        rows = response.get('rows', [])
        data = []
        for row in rows:
            data.append({
                'query': row['keys'][0],
                'clicks': row['clicks'],
                'impressions': row['impressions'],
                'ctr': row['ctr'] * 100,
                'position': row['position']
            })
        
        return data
    
    async def fetch_pages(self, start_date: str, end_date: str, limit: int = 50) -> List[Dict]:
        """Fetch top content pages"""
        service = self.get_service()
        
        request = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': ['page'],
            'rowLimit': limit
        }
        
        response = service.searchanalytics().query(
            siteUrl=GSC_SITE_URL,
            body=request
        ).execute()
        
        rows = response.get('rows', [])
        data = []
        for row in rows:
            data.append({
                'page': row['keys'][0],
                'clicks': row['clicks'],
                'impressions': row['impressions'],
                'ctr': row['ctr'] * 100,
                'position': row['position']
            })
        
        return data
    
    async def fetch_countries(self, start_date: str, end_date: str, limit: int = 20) -> List[Dict]:
        """Fetch top countries"""
        service = self.get_service()
        
        request = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': ['country'],
            'rowLimit': limit
        }
        
        response = service.searchanalytics().query(
            siteUrl=GSC_SITE_URL,
            body=request
        ).execute()
        
        rows = response.get('rows', [])
        data = []
        for row in rows:
            data.append({
                'country': row['keys'][0],
                'clicks': row['clicks'],
                'impressions': row['impressions'],
                'ctr': row['ctr'] * 100,
                'position': row['position']
            })
        
        return data
    
    async def fetch_devices(self, start_date: str, end_date: str) -> List[Dict]:
        """Fetch by device"""
        service = self.get_service()
        
        request = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': ['device'],
            'rowLimit': 10
        }
        
        response = service.searchanalytics().query(
            siteUrl=GSC_SITE_URL,
            body=request
        ).execute()
        
        rows = response.get('rows', [])
        data = []
        for row in rows:
            data.append({
                'device': row['keys'][0],
                'clicks': row['clicks'],
                'impressions': row['impressions'],
                'ctr': row['ctr'] * 100,
                'position': row['position']
            })
        
        return data
    
    async def fetch_all_data(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Fetch all GSC data concurrently"""
        trend, queries, pages, countries, devices = await asyncio.gather(
            self.fetch_trend(start_date, end_date),
            self.fetch_queries(start_date, end_date),
            self.fetch_pages(start_date, end_date),
            self.fetch_countries(start_date, end_date),
            self.fetch_devices(start_date, end_date)
        )
        
        # Calculate totals
        total_clicks = sum(d['clicks'] for d in trend)
        total_impressions = sum(d['impressions'] for d in trend)
        avg_ctr = sum(d['ctr'] for d in trend) / len(trend) if trend else 0
        avg_position = sum(d['position'] for d in trend) / len(trend) if trend else 0
        
        return {
            'summary': {
                'total_clicks': total_clicks,
                'total_impressions': total_impressions,
                'avg_ctr': avg_ctr,
                'avg_position': avg_position,
                'days': len(trend)
            },
            'trend': trend,
            'queries': queries,
            'pages': pages,
            'countries': countries,
            'devices': devices,
            'fetched_at': datetime.now().isoformat()
        }
    
    def invalidate_cache(self):
        """Clear cache"""
        self._data_cache = None
        self._last_fetch = None


# Global instance
gsc_client = GSCAsyncClient()


async def fetch_gsc_data(start_date: str, end_date: str) -> Dict[str, Any]:
    """Fetch all GSC data"""
    return await gsc_client.fetch_all_data(start_date, end_date)


if __name__ == "__main__":
    async def test():
        result = await fetch_gsc_data('2025-11-01', '2026-02-28')
        print(f"Summary: {result['summary']}")
        print(f"Top Queries: {len(result['queries'])}")
        print(f"Top Pages: {len(result['pages'])}")
    
    asyncio.run(test())
