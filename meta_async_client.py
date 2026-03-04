"""
Async Meta (Facebook) API Client - High-performance data fetching
"""
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

import streamlit as st

# ==================== CONFIGURATION ====================
try:
    ACCESS_TOKEN = st.secrets["meta"]["access_token"]
    APP_ID = st.secrets["meta"]["app_id"]
    APP_SECRET = st.secrets["meta"]["app_secret"]
    AD_ACCOUNT_ID = st.secrets["meta"]["ad_account_id"]
except:
    ACCESS_TOKEN = "EAAWYAtm7TKsBQwh69TXCFXf1Q7r921FVx88zWvUPRC7xswAgTrG04gb7YmsMKZBjfTxzAhA9fAlbsrOjvcmpVFa89GBgAuCoef7ntpmZCVflyKASFb0zfoNep6I4zblPVDd0B3ZC46JIKxdpivP1xfXoPXW2L74ZAf1LAmtqzD2RXOExECsKBZCx6mschJM3AIveI"
    APP_ID = "1574512893840555"
    APP_SECRET = "2f2984631ab5a1dd0606a8d09e45f100"
    AD_ACCOUNT_ID = "act_600555439172695"

BASE_URL = "https://graph.facebook.com/v18.0"


class MetaAsyncClient:
    """Async Meta Ads API Client"""
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._campaigns_cache: Optional[List[Dict]] = None
        self._last_fetch: Optional[datetime] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=50, limit_per_host=20)
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )
        return self._session
    
    async def close(self):
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def fetch_campaigns(self, start_date: str, end_date: str, breakdown: str = None) -> List[Dict]:
        """Fetch all campaign insights
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            breakdown: Optional breakdown dimension (e.g., 'country' for country-level data)
        """
        # Cache key includes breakdown to support different views
        cache_key = f"{start_date}_{end_date}_{breakdown}"
        if self._campaigns_cache is not None and hasattr(self, '_cache_key') and self._cache_key == cache_key:
            return self._campaigns_cache
        
        session = await self.get_session()
        
        # Meta Ads API endpoint
        url = f"{BASE_URL}/{AD_ACCOUNT_ID}/insights"
        
        # Build fields list
        fields = 'campaign_name,campaign_id,reach,frequency,impressions,spend,cpm,clicks,ctr,cpc,inline_link_clicks,inline_link_click_ctr,actions,action_values,cost_per_action_type'
        
        params = {
            'access_token': ACCESS_TOKEN,
            'level': 'campaign',
            'time_range': json.dumps({'since': start_date, 'until': end_date}),
            'fields': fields,
            'filtering': json.dumps([{'field': 'campaign.effective_status', 'operator': 'IN', 'value': ['ACTIVE', 'PAUSED']}]),
            'limit': 500
        }

        if breakdown == 'country':
            params['breakdowns'] = 'country'
            # Note: For breakdowns, Meta allows adding the dimension to fields to get the value in the response
            params['fields'] += ',country'
        
        all_data = []
        after_cursor = None
        
        while True:
            query_params = params.copy()
            if after_cursor:
                query_params['after'] = after_cursor
            
            try:
                async with session.get(url, params=query_params) as response:
                    if response.status != 200:
                        text = await response.text()
                        print(f"Error {response.status}: {text}")
                        break
                    
                    data = await response.json()
                    campaigns = data.get('data', [])
                    
                    if not campaigns:
                        break
                    
                    all_data.extend(campaigns)
                    
                    # Check for pagination
                    paging = data.get('paging', {})
                    cursors = paging.get('cursors', {})
                    after_cursor = cursors.get('after')
                    
                    if not after_cursor:
                        break
                        
            except Exception as e:
                print(f"Error fetching campaigns: {e}")
                break
        
        # Process the data
        processed = []
        for entry in all_data:
            actions = entry.get('actions', [])
            costs = entry.get('cost_per_action_type', [])
            
            def get_act(name):
                return sum(float(a['value']) for a in actions if a['action_type'] == name)
            
            def get_cost(name):
                return next((float(a['value']) for a in costs if a['action_type'] == name), 0)
            
            # Results logic
            lead_forms = get_act('lead')
            # Safe check for action_type in case it is None
            web_conversions = sum(float(a['value']) for a in actions if 'offsite_conversion' in (a.get('action_type') or ''))
            final_results = int(lead_forms if lead_forms > 0 else (lead_forms + web_conversions))
            
            processed.append({
                'campaign_id': entry.get('campaign_id'),
                'campaign_name': entry.get('campaign_name'),
                'results': final_results,
                'reach': entry.get('reach'),
                'frequency': float(entry.get('frequency', 0)),
                'impressions': entry.get('impressions'),
                'spend': float(entry.get('spend', 0)),
                'cpm': float(entry.get('cpm', 0)),
                'clicks': entry.get('clicks'),
                'ctr': float(entry.get('ctr', 0)),
                'cpc': float(entry.get('cpc', 0)),
                'link_clicks': entry.get('inline_link_clicks'),
                'link_ctr': float(entry.get('inline_link_click_ctr', 0)),
                'leads': int(lead_forms),
                'web_conversions': int(web_conversions),
                'cost_per_lead': get_cost('lead') or get_cost('offsite_conversion.fb_pixel_purchase') or 0,
                'country': entry.get('country', 'Unknown')
            })
        
        self._campaigns_cache = processed
        self._cache_key = cache_key
        self._last_fetch = datetime.now()
        return processed
    
    async def fetch_campaigns_by_country(self, start_date: str, end_date: str) -> List[Dict]:
        """Fetch campaign data broken down by country"""
        return await self.fetch_campaigns(start_date, end_date, breakdown='country')
    
    def invalidate_cache(self):
        """Clear cache"""
        self._campaigns_cache = None
        self._cache_key = None
        self._last_fetch = None


# Global instance
meta_client = MetaAsyncClient()


async def fetch_meta_data(start_date: str, end_date: str) -> Dict[str, Any]:
    """Fetch all Meta data"""
    campaigns = await meta_client.fetch_campaigns(start_date, end_date)
    
    # Calculate totals
    total_spend = sum(c['spend'] for c in campaigns)
    total_leads = sum(c['results'] for c in campaigns)
    total_impressions = sum(int(c['impressions'] or 0) for c in campaigns)
    total_clicks = sum(int(c['clicks'] or 0) for c in campaigns)
    
    return {
        'campaigns': campaigns,
        'summary': {
            'total_spend': total_spend,
            'total_leads': total_leads,
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'avg_ctr': (total_clicks / total_impressions * 100) if total_impressions > 0 else 0,
            'cpl': (total_spend / total_leads) if total_leads > 0 else 0,
            'campaign_count': len(campaigns)
        },
        'fetched_at': datetime.now().isoformat()
    }


if __name__ == "__main__":
    async def test():
        result = await fetch_meta_data('2025-11-01', '2026-02-28')
        print(f"Fetched {len(result['campaigns'])} campaigns")
        print(f"Summary: {result['summary']}")
    
    asyncio.run(test())
