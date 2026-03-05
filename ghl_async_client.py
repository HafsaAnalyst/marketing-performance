"""
Async GHL API Client - High-performance data fetching without CSV/database
Uses aiohttp for concurrent async requests
"""
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

import streamlit as st

# ==================== CONFIGURATION ====================
try:
    GHL_API_KEY = st.secrets["ghl"]["api_key"]
    GHL_LOCATION_ID = st.secrets["ghl"]["location_id"]
except:
    GHL_API_KEY = "pit-0ca0568a-d707-46f3-a018-95a9c1a00c3f"
    GHL_LOCATION_ID = "Cy61ZIoB1Q68krX0lSZA"

GHL_VERSION = "2021-07-28"
BASE_URL = "https://services.leadconnectorhq.com"

import pytz

HEADERS = {
    "Authorization": f"Bearer {GHL_API_KEY}",
    "Version": GHL_VERSION,
    "Accept": "application/json"
}

def convert_to_aedt(iso_str):
    if not iso_str: return None
    try:
        if 'Z' in iso_str:
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(iso_str)
        aedt = pytz.timezone('Australia/Sydney')
        return dt.astimezone(aedt).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return iso_str

# Consultant mapping from ghl.py
CONSULTANTS = {
    "uwCBo7Y0cAWLs6ZqPjJI": "Turab - Career Counsellor",
    "RF7bh7b3avrzStoTE8ho": "Kajal - Education Consultant",
    "epTOwlPOplgGqgy9aFEY": "Minhaz - Education Consultant",
    "hkL937P7e6XTzy58dOZ7": "Navneet Kaur - Education Consultant",
    "hsCSqcYHrXwL55NffEFi": "Wajahad - Education Consultant",
    "vjmOhJPIT4pAPzCyCmdT": "Saurab - Education Consultant",
    "Zyrz08TZ6BaAruWxERy5": "Nasir Nawaz - MARA Certified",
    "gttsLvMBPKFfslnOuwHT": "Nasir Nawaz - MARA Certified - Online",
    "3sB0LoMibhbr9eUktA7i": "Faheem - Education Consultant",
    "hsVntQS9KwIw8eF4D8ef": "Gurbir Singh - MARA Certified - Online",
    "o4AfsJ45rEkewmENut12": "Gurbir Singh - MARA Certified - Onsite"
}


class GHLAsyncClient:
    """Async GHL API Client with connection pooling"""
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._contacts_cache: Optional[List[Dict]] = None
        self._opportunities_cache: Optional[List[Dict]] = None
        self._appointments_cache: Optional[List[Dict]] = None
        self._pipelines_cache: Optional[List[Dict]] = None
        self._users_cache: Optional[List[Dict]] = None
        self._consultants_cache: Optional[List[Dict]] = None
        self._last_fetch: Optional[datetime] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connection pooling"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,  # Max connections
                limit_per_host=50,  # Max per host
                ttl_dns_cache=300,  # DNS cache TTL
                enable_cleanup_closed=True
            )
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=HEADERS
            )
        return self._session
    
    async def close(self):
        """Close the aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _fetch_with_pagination(
        self, 
        url: str, 
        params: Dict = None,
        data_key: str = "contacts",
        max_pages: int = None
    ) -> List[Dict]:
        """Generic paginated fetch - NO LIMITS, fetches ALL data"""
        session = await self.get_session()
        all_items = []
        start_after = None
        start_after_id = None
        page_count = 0
        
        while True:
            query_params = params.copy() if params else {}
            if start_after and start_after_id:
                # GHL requires BOTH startAfter (timestamp) and startAfterId to paginate
                query_params["startAfter"] = start_after
                query_params["startAfterId"] = start_after_id
            
            try:
                async with session.get(url, params=query_params) as response:
                    if response.status != 200:
                        print(f"Error {response.status}: {await response.text()}")
                        break
                    
                    data = await response.json()
                    items = data.get(data_key, [])
                    
                    if not items:
                        break
                    
                    all_items.extend(items)
                    page_count += 1
                    
                    # Get next page cursor - GHL needs both startAfter and startAfterId
                    meta = data.get("meta", {})
                    start_after = meta.get("startAfter")
                    start_after_id = meta.get("startAfterId")
                    
                    if not start_after or not start_after_id:
                        break
                    
                    # Optional max pages limit for safety
                    if max_pages and page_count >= max_pages:
                        print(f"Reached max pages: {max_pages}")
                        break
                    
                    if page_count % 50 == 0:
                        print(f"  ... fetched {len(all_items)} {data_key} ({page_count} pages)")
                        
            except aiohttp.ClientError as e:
                print(f"Client error: {e}")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                break
        
        print(f"Fetched {len(all_items)} items in {page_count} pages")
        return all_items

    
    async def _fetch_with_start_after(
        self,
        url: str,
        params: Dict = None,
        data_key: str = "opportunities",
        max_pages: int = None
    ) -> List[Dict]:
        """Fetch with startAfterId/startAfter pagination (for opportunities)"""
        session = await self.get_session()
        all_items = []
        start_after_id = None
        start_after = None
        page_count = 0
        
        while True:
            query_params = params.copy() if params else {}
            if start_after_id and start_after:
                query_params["startAfterId"] = start_after_id
                query_params["startAfter"] = start_after
            
            try:
                async with session.get(url, params=query_params) as response:
                    if response.status != 200:
                        print(f"Error {response.status}: {await response.text()}")
                        break
                    
                    data = await response.json()
                    items = data.get(data_key, [])
                    
                    if not items:
                        break
                    
                    all_items.extend(items)
                    page_count += 1
                    
                    # Get next page cursors
                    meta = data.get("meta", {})
                    start_after_id = meta.get("nextPageId") or meta.get("startAfterId")
                    start_after = meta.get("nextPageStart") or meta.get("startAfter")
                    
                    if not start_after_id:
                        break
                    
                    if max_pages and page_count >= max_pages:
                        break
                        
            except Exception as e:
                print(f"Error: {e}")
                break
        
        print(f"Fetched {len(all_items)} items in {page_count} pages")
        return all_items
    
    # ==================== MAIN FETCH METHODS ====================
    
    async def fetch_all_contacts(self) -> List[Dict]:
        """Fetch ALL contacts - no limits, no date filtering"""
        if self._contacts_cache is not None:
            print(f"Using cached contacts: {len(self._contacts_cache)}")
            return self._contacts_cache
        
        url = f"{BASE_URL}/contacts/"
        params = {"locationId": GHL_LOCATION_ID, "limit": 100}
        
        contacts = await self._fetch_with_pagination(
            url, params, 
            data_key="contacts"
        )
        
        self._contacts_cache = contacts
        self._last_fetch = datetime.now()
        return contacts
    
    async def fetch_all_opportunities(self) -> List[Dict]:
        """Fetch ALL opportunities - no limits"""
        if self._opportunities_cache is not None:
            print(f"Using cached opportunities: {len(self._opportunities_cache)}")
            return self._opportunities_cache
        
        url = f"{BASE_URL}/opportunities/search"
        params = {"location_id": GHL_LOCATION_ID, "limit": 100}
        
        opportunities = await self._fetch_with_start_after(
            url, params,
            data_key="opportunities"
        )
        
        self._opportunities_cache = opportunities
        self._last_fetch = datetime.now()
        return opportunities
    
    async def fetch_all_appointments(self, start_date: str = "2025-11-01", end_date: str = None) -> List[Dict]:
        """Fetch ALL appointments by iterating over all known consultants"""
        if self._appointments_cache is not None:
            print(f"Using cached appointments: {len(self._appointments_cache)}")
            return self._appointments_cache
        
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        # GHL requires milliseconds for startTime/endTime
        start_ms = int(datetime.strptime(f"{start_date} 00:00:00", "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
        end_ms = int(datetime.strptime(f"{end_date} 23:59:59", "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

        session = await self.get_session()
        
        async def fetch_for_calendar(cal_id: str, name: str) -> List[Dict]:
            url = f"{BASE_URL}/calendars/events"
            params = {
                "locationId": GHL_LOCATION_ID,
                "calendarId": cal_id,
                "startTime": start_ms,
                "endTime": end_ms
            }
            
            cal_events = []
            start_after_id = None
            start_after = None
            
            while True:
                query_params = params.copy()
                if start_after_id and start_after:
                    query_params["startAfterId"] = start_after_id
                    query_params["startAfter"] = start_after
                
                try:
                    async with session.get(url, params=query_params) as response:
                        if response.status != 200:
                            break
                        
                        data = await response.json()
                        events = data.get("events", [])
                        if not events:
                            break
                        
                        cal_events.extend(events)
                        
                        meta = data.get("meta", {})
                        start_after_id = meta.get("nextPageId") or meta.get("startAfterId")
                        start_after = meta.get("nextPageStart") or meta.get("startAfter")
                        
                        if not start_after_id:
                            break
                except Exception as e:
                    print(f"Error fetching for {name}: {e}")
                    break
            return cal_events

        # Fetch for all consultants in parallel
        tasks = [fetch_for_calendar(cal_id, name) for cal_id, name in CONSULTANTS.items()]
        results = await asyncio.gather(*tasks)
        
        all_events = []
        for r in results:
            all_events.extend(r)
        
        self._appointments_cache = all_events
        self._last_fetch = datetime.now()
        return all_events
            
    
    async def fetch_pipelines(self) -> List[Dict]:
        """Fetch all pipelines"""
        if self._pipelines_cache is not None:
            return self._pipelines_cache
        
        session = await self.get_session()
        url = f"{BASE_URL}/opportunities/pipelines"
        params = {"locationId": GHL_LOCATION_ID}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self._pipelines_cache = data.get("pipelines", [])
                else:
                    self._pipelines_cache = []
        except Exception as e:
            print(f"Error fetching pipelines: {e}")
            self._pipelines_cache = []
        
        return self._pipelines_cache
    
    async def fetch_users(self) -> List[Dict]:
        """Fetch all users"""
        if self._users_cache is not None:
            return self._users_cache
        
        session = await self.get_session()
        url = f"{BASE_URL}/users/"
        params = {"locationId": GHL_LOCATION_ID}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self._users_cache = data.get("users", [])
                else:
                    self._users_cache = []
        except Exception as e:
            print(f"Error fetching users: {e}")
            self._users_cache = []
        
        return self._users_cache
    
    async def fetch_consultant_metrics(self, start_date: str = "2025-11-01", end_date: str = None, opportunities: List[Dict] = None) -> List[Dict]:
        """Fetch consultant appointment metrics and cross-reference with opportunities"""
        # Ensure we have the raw appointments first
        all_events = await self.fetch_all_appointments(start_date, end_date)
        
        # Build opportunity stats by consultant name
        opp_stats = {}
        if opportunities:
            for opp in opportunities:
                owner = opp.get("owner")
                if owner and owner != "Unassigned":
                    if owner not in opp_stats:
                        opp_stats[owner] = {"won_count": 0, "total_value": 0}
                    if opp.get("status") == "won":
                        opp_stats[owner]["won_count"] += 1
                    opp_stats[owner]["total_value"] += float(opp.get("value", 0))

        # Now process stats per consultant
        consultant_results = []
        for cal_id, name in CONSULTANTS.items():
            # Filter events for this consultant
            cal_events = [e for e in all_events if e.get("calendarId") == cal_id]
            
            # Count statuses
            confirmed = sum(1 for e in cal_events if e.get("appointmentStatus", "").lower() == "confirmed")
            show = sum(1 for e in cal_events if e.get("appointmentStatus", "").lower() in ["showed", "show"])
            no_show = sum(1 for e in cal_events if e.get("appointmentStatus", "").lower() in ["noshow", "no-show", "no show"])
            unconfirmed = sum(1 for e in cal_events if e.get("appointmentStatus", "").lower() in ["new", "unconfirmed", ""])
            
            # Extract amount paid if possible, otherwise default 0
            # Since GHL Events API doesn't expose payment details directly, will sum to 0.
            amount_paid = 0

            consultant_results.append({
                "consultant_name": name,
                "calendar_id": cal_id,
                "total_appointments": len(cal_events),
                "amount_paid": amount_paid,
                "confirmed": confirmed,
                "show": show,
                "no_show": no_show,
                "unconfirmed": unconfirmed,
                "busy_slots": len(cal_events),
                "empty_spaces": max(0, 14 - len(cal_events)),
                "max_capacity": 14,
                "events": cal_events
            })
        
        self._consultants_cache = consultant_results
        return consultant_results

    async def fetch_consultant_pulse(self, opportunities: List[Dict]) -> Dict[str, List[Dict]]:
        """Fetch Today and Weekly metrics for scoreboard"""
        # 1. Fetch Today
        today = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')
        today_res = await self.fetch_consultant_metrics(start_date=today_str, end_date=today_str, opportunities=opportunities)
        for dr in today_res: dr['Type'] = 'Today'

        # 2. Fetch Weekly
        start_of_week = today - timedelta(days=today.weekday()) # Monday
        end_of_week = start_of_week + timedelta(days=4) # Friday
        weekly_res = await self.fetch_consultant_metrics(
            start_date=start_of_week.strftime('%Y-%m-%d'),
            end_date=end_of_week.strftime('%Y-%m-%d'),
            opportunities=opportunities
        )
        for dr in weekly_res: dr['Type'] = 'Weekly'

        return {
            "today": today_res,
            "weekly": weekly_res
        }
    
    # ==================== COMBINED FETCH ====================
    
    async def fetch_all_data(self, start_date: str = "2025-11-01", end_date: str = None) -> Dict[str, Any]:
        """Fetch ALL data concurrently - FASTEST approach"""
        print(f"Fetching GHL data from {start_date} to {end_date}...")
        
        # Ensure end_date
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # Fetch core data in parallel
        contacts_raw, opportunities_raw, pipelines, users = await asyncio.gather(
            self.fetch_all_contacts(),
            self.fetch_all_opportunities(),
            self.fetch_pipelines(),
            self.fetch_users()
        )
        
        # Merge opportunities so we have names/values for metrics
        merged_opps = merge_opportunity_data(opportunities_raw, pipelines, users, contacts_raw)
        
        # Now fetch consultant pulse (Today/Weekly)
        consultant_pulse = await self.fetch_consultant_pulse(opportunities=merged_opps)
        
        # appointments for the original range
        appointments = await self.fetch_all_appointments(start_date, end_date)
        
        return {
            "contacts": contacts_raw,
            "opportunities": merged_opps, # Return merged
            "appointments": appointments,
            "pipelines": pipelines,
            "users": users,
            "consultants_today": consultant_pulse["today"],
            "consultants_weekly": consultant_pulse["weekly"],
            "fetched_at": datetime.now().isoformat(),
            "counts": {
                "contacts": len(contacts_raw),
                "opportunities": len(merged_opps),
                "appointments": len(appointments),
                "consultants_today": len(consultant_pulse["today"]),
                "consultants_weekly": len(consultant_pulse["weekly"])
            }
        }
    
    def invalidate_cache(self):
        """Clear all caches to force fresh fetch"""
        self._contacts_cache = None
        self._opportunities_cache = None
        self._appointments_cache = None
        self._pipelines_cache = None
        self._users_cache = None
        self._consultants_cache = None
        self._last_fetch = None
        print("Cache invalidated")


# ==================== GLOBAL CLIENT INSTANCE ====================
ghl_client = GHLAsyncClient()


# ==================== HELPER FUNCTIONS ====================

def build_pipeline_map(pipelines: List[Dict]) -> Dict[str, str]:
    """Build pipeline ID to name map"""
    return {p["id"]: p["name"] for p in pipelines}


def build_stage_map(pipelines: List[Dict]) -> Dict[str, str]:
    """Build stage ID to name map"""
    stage_map = {}
    for p in pipelines:
        for stage in p.get("stages", []):
            stage_map[stage["id"]] = stage["name"]
    return stage_map


def build_user_map(users: List[Dict]) -> Dict[str, str]:
    """Build user ID to name map"""
    return {
        u["id"]: f"{u.get('firstName', '')} {u.get('lastName', '')}".strip() 
        for u in users
    }


def merge_contact_data(
    contacts: List[Dict],
    opportunities: List[Dict],
    appointments: List[Dict],
    pipelines: List[Dict],
    users: List[Dict]
) -> List[Dict]:
    """Merge all data for contacts - FAST in-memory join"""
    
    # Build lookup maps
    pipeline_map = build_pipeline_map(pipelines)
    stage_map = build_stage_map(pipelines)
    user_map = build_user_map(users)
    
    # Build opportunity lookup by contactId
    opp_by_contact = {opp.get("contactId"): opp for opp in opportunities}
    
    # Build appointment lookup by contactId (latest)
    appt_by_contact = {}
    for appt in appointments:
        contact_id = appt.get("contactId")
        if contact_id:
            existing = appt_by_contact.get(contact_id)
            appt_time = appt.get("startTime", "")
            if not existing or appt_time > existing.get("startTime", ""):
                appt_by_contact[contact_id] = appt
    
    # Merge
    merged = []
    for c in contacts:
        c_id = c.get("id")
        
        # Get opportunity
        opp = opp_by_contact.get(c_id, {})
        p_id = opp.get("pipelineId")
        s_id = opp.get("pipelineStageId")
        
        # Get appointment
        appt = appt_by_contact.get(c_id)
        
        # Get attribution
        attr = c.get("attributions", [])
        first_attr = attr[0] if attr else {}
        latest_attr = attr[-1] if attr else {}
        
        merged.append({
            "contact_id": c_id,
            "contact_name": c.get("contactName"),
            "email": c.get("email"),
            "phone": c.get("phone"),
            "contact_created": c.get("dateAdded", "")[:10] if c.get("dateAdded") else None,
            "Created (AEDT)": convert_to_aedt(c.get("dateAdded")),
            "dateAdded_raw": c.get("dateAdded"),
            "createdAt_raw": c.get("createdAt"),
            "createdAt_date": c.get("createdAt", "")[:10] if c.get("createdAt") else None,
            "Created_createdAt (AEDT)": convert_to_aedt(c.get("createdAt")),
            "last_activity": c.get("dateUpdated", "")[:10] if c.get("dateUpdated") else None,
            "dateUpdated_raw": c.get("dateUpdated"),
            "source": c.get("source"),
            "assigned_to": user_map.get(c.get("assignedTo"), "Unassigned") if c.get("assignedTo") else "Unassigned",
            # Opportunity data
            "opportunity_id": opp.get("opportunity_id", opp.get("id")),
            "opportunity_name": opp.get("opportunity_name", opp.get("name")),
            "opportunity_status": opp.get("status", opp.get("opportunity_status")),
            "opportunity_value": opp.get("value", opp.get("monetaryValue", 0)),
            "pipeline": opp.get("pipeline", pipeline_map.get(p_id, "Unknown") if p_id else None),
            "stage": opp.get("stage", stage_map.get(s_id, "Unknown") if s_id else None),
            "opportunity_created": opp.get("created_date") or (opp.get("createdAt", "")[:10] if opp.get("createdAt") else None),
            # Appointment data
            "appointment_date": appt.get("startTime", "")[:10] if appt else None,
            "appointment_time": appt.get("startTime", "") if appt else None,
            "appointment_status": appt.get("appointmentStatus") if appt else None,
            # Attribution
            "first_attribution": first_attr.get("utmSessionSource", "Direct") if first_attr else "Direct",
            "latest_attribution": latest_attr.get("utmSessionSource", "Direct") if latest_attr else "Direct",
            # Location data
            "city": c.get("city"),
            "country": c.get("country"),
            "state": c.get("state")
        })
    
    return merged


def merge_opportunity_data(
    opportunities: List[Dict],
    pipelines: List[Dict],
    users: List[Dict],
    contacts: List[Dict] = []
) -> List[Dict]:
    """Merge opportunity data with pipeline stages, users, and contact details"""
    
    stage_map = build_stage_map(pipelines)
    user_map = build_user_map(users)
    pipeline_map = build_pipeline_map(pipelines)
    
    # Create map of contacts for faster geo lookups
    contact_map = {c.get("id"): c for c in contacts if c.get("id")}
    
    merged = []
    for opp in opportunities:
        p_id = opp.get("pipelineId")
        s_id = opp.get("pipelineStageId")
        contact_id = opp.get("contactId")
        
        stage_name = stage_map.get(s_id, "Unknown")
        contact = opp.get("contact", {})
        
        # Get extended contact
        ext_contact = contact_map.get(contact_id, {})
        city = ext_contact.get("city") or contact.get("city")
        country = ext_contact.get("country") or contact.get("country")
        
        merged.append({
            "opportunity_id": opp.get("id"),
            "contactId": contact_id,
            "opportunity_name": opp.get("name"),
            "contact_name": contact.get("name"),
            "contact_email": contact.get("email"),
            "status": opp.get("status"),
            "value": opp.get("monetaryValue", 0),
            "pipeline": pipeline_map.get(p_id),
            "stage": stage_name,
            "days_in_pipeline": opp.get("days", 0),
            "owner": user_map.get(opp.get("assignedTo"), "Unassigned"),
            "tags": ", ".join(opp.get("tags", [])),
            "source": opp.get("source"),
            "city": city,
            "country": country,
            "country_lowercase": str(country).lower() if country else None,
            "created_date": opp.get("createdAt", "")[:10] if opp.get("createdAt") else None,
            "Created On (AEDT)": convert_to_aedt(opp.get("createdAt")),
            "updated_date": opp.get("updatedAt", "")[:10] if opp.get("updatedAt") else None,
            "Updated On (AEDT)": convert_to_aedt(opp.get("updatedAt")),
            "lost_reason": opp.get("lostReason")
        })
    
    return merged


# ==================== TEST FUNCTION ====================

async def test_async_client():
    """Test the async client"""
    client = GHLAsyncClient()
    try:
        data = await client.fetch_all_data()
        print(f"\nFetched successfully:")
        print(f"   Contacts: {len(data['contacts'])}")
        print(f"   Opportunities: {len(data['opportunities'])}")
        print(f"   Appointments: {len(data['appointments'])}")
        print(f"   Pipelines: {len(data['pipelines'])}")
        print(f"   Users: {len(data['users'])}")
        print(f"   Consultants: {len(data['consultants'])}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_async_client())
