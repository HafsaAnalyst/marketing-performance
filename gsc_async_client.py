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
    
    # Set environment variable for library preference
    if os.path.exists("google_creds.json"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath("google_creds.json")
    elif os.path.exists("service_account.json"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath("service_account.json")

    try:
        if "google" in st.secrets and st.secrets["google"] is not None:
            if "gsc_credentials" in st.secrets["google"]:
                secret = st.secrets["google"]["gsc_credentials"]
                if isinstance(secret, str):
                    return service_account.Credentials.from_service_account_info(json.loads(secret), scopes=scopes)
                return service_account.Credentials.from_service_account_info(dict(secret), scopes=scopes)
    except Exception as e:
        print(f"Secrets Credential Error: {e}")
        pass
    
    if os.path.exists("google_creds.json"): # Prefer GSC-specific creds
        return service_account.Credentials.from_service_account_file("google_creds.json", scopes=scopes)
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

    def _execute_request(self, request_obj):
        """Helper to execute GSC requests and handle HttpErrors with details"""
        try:
            return request_obj.execute()
        except Exception as e:
            error_details = str(e)
            # Check for HttpError from googleapiclient
            if "HttpError" in str(type(e)):
                if hasattr(e, 'content'):
                    try:
                        error_json = json.loads(e.content.decode('utf-8'))
                        error_details = error_json.get('error', {}).get('message', error_details)
                    except:
                        pass
                print(f"GSC API Error for {GSC_SITE_URL}: {error_details}")
                # Re-raise as a standard Exception with the clear message
                raise Exception(f"Google API Error: {error_details}")
            raise e
    
    async def fetch_trend(self, start_date: str, end_date: str) -> List[Dict]:
        """Fetch daily trend data with country dimension"""
        service = self.get_service()
        request = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': ['date', 'country'],
            'rowLimit': 5000
        }
        response = self._execute_request(service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=request))
        rows = response.get('rows', [])
        data = []
        for row in rows:
            data.append({
                'keys': row['keys'], # [date, country]
                'clicks': row['clicks'],
                'impressions': row['impressions'],
                'ctr': row['ctr'],
                'position': row['position']
            })
        return data
    
    async def fetch_queries(self, start_date: str, end_date: str, limit: int = 200) -> List[Dict]:
        """Fetch top search queries with country dimension"""
        service = self.get_service()
        request = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': ['query', 'country'],
            'rowLimit': limit
        }
        response = self._execute_request(service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=request))
        rows = response.get('rows', [])
        data = []
        for row in rows:
            data.append({
                'keys': row['keys'], # [query, country]
                'clicks': row['clicks'],
                'impressions': row['impressions'],
                'ctr': row['ctr'],
                'position': row['position']
            })
        return data
    
    async def fetch_pages(self, start_date: str, end_date: str, limit: int = 200) -> List[Dict]:
        """Fetch top content pages with country dimension"""
        service = self.get_service()
        request = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': ['page', 'country'],
            'rowLimit': limit
        }
        response = self._execute_request(service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=request))
        rows = response.get('rows', [])
        data = []
        for row in rows:
            data.append({
                'keys': row['keys'], # [page, country]
                'clicks': row['clicks'],
                'impressions': row['impressions'],
                'ctr': row['ctr'],
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
        
        response = self._execute_request(service.searchanalytics().query(
            siteUrl=GSC_SITE_URL,
            body=request
        ))
        
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
        
        response = self._execute_request(service.searchanalytics().query(
            siteUrl=GSC_SITE_URL,
            body=request
        ))
        
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
        
        # Weighted Average CTR and Position - or just simple account-level query if needed
        # But for now, simple average of the daily-country rows
        avg_ctr = sum(d['ctr'] for d in trend) / len(trend) if trend else 0
        avg_position = sum(d['position'] for d in trend) / len(trend) if trend else 0
        
        return {
            'summary': {
                'total_clicks': total_clicks,
                'total_impressions': total_impressions,
                'avg_ctr': avg_ctr * 100,
                'avg_position': avg_position,
                'days': len(set(d['keys'][0] for d in trend)) if trend else 0
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
