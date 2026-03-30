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
    GHL_API_KEY = None
    GHL_LOCATION_ID = None

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
        self._calendars_cache: Optional[List[Dict]] = None
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
    
    async def fetch_payments(self, start_date: str, end_date: str) -> List[Dict]:
        """Fetch ALL payment transactions for the given range"""
        url = f"{BASE_URL}/payments/transactions"
        # GHL payment transactions endpoint may use different param names or locationId
        params = {
            "locationId": GHL_LOCATION_ID,
            "limit": 100,
            # GHL v2 transactions might use startTime/endTime or similar
            # If start_date/end_date are passed, we'll try to filter
        }
        
        try:
            payments = await self._fetch_with_pagination(
                url, params, 
                data_key="transactions"
            )
            return payments
        except:
            return []
            
    async def fetch_all_calendars(self) -> List[Dict]:
        """Fetch ALL calendars for the location"""
        if self._calendars_cache is not None:
            return self._calendars_cache
        
        url = f"{BASE_URL}/calendars/"
        params = {"locationId": GHL_LOCATION_ID}
        
        try:
            # Calendar API often returns list in "calendars"
            session = await self.get_session()
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self._calendars_cache = data.get("calendars", [])
                else:
                    self._calendars_cache = []
        except Exception as e:
            print(f"Error fetching calendars: {e}")
            self._calendars_cache = []
            
        return self._calendars_cache
    
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
        if hasattr(self, "_appt_cache_range") and self._appt_cache_range == (start_date, end_date):
            return self._appointments_cache
        
        # Reset cache if range changed
        self._appt_cache_range = (start_date, end_date)
        self._appointments_cache = None
        
        # GHL requires milliseconds for startTime/endTime (localized to Sydney)
        tz = pytz.timezone('Australia/Sydney')
        start_dt = tz.localize(datetime.strptime(f"{start_date} 00:00:00", "%Y-%m-%d %H:%M:%S"))
        end_dt = tz.localize(datetime.strptime(f"{end_date} 23:59:59", "%Y-%m-%d %H:%M:%S"))
        
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)

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
                            print(f"[GHL ERROR] Failed fetch for {name}: {response.status} - {await response.text()}")
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

        # Dynamically discover all calendars
        all_calendars = await self.fetch_all_calendars()
        
        # Merge hardcoded names with dynamically fetched ones
        discovery_map = {c.get("id"): c.get("name") for c in all_calendars if c.get("id")}
        discovery_map.update(CONSULTANTS) # Hardcoded ones might have better display names
        
        all_tasks = [fetch_for_calendar(cal_id, name) for cal_id, name in discovery_map.items()]
        all_results = await asyncio.gather(*all_tasks)
        
        merged_events = []
        for res in all_results:
            merged_events.extend(res)
            
        self._appointments_cache = merged_events
        self._last_fetch = datetime.now()
        return merged_events
            
    
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
    
    async def fetch_consultant_metrics(self, start_date: str, end_date: str, opportunities: List[Dict], contacts: List[Dict], payments: List[Dict], working_days: int = 1) -> List[Dict]:
        """Fetch consultant appointment metrics and cross-reference with opportunities/payments/contacts"""
        # Ensure we have the raw appointments first
        all_events = await self.fetch_all_appointments(start_date, end_date)
        
        # Build contact lookup for phone/country
        contact_map = {c.get("id"): c for c in (contacts or []) if c.get("id")}
        
        # Build payment lookup by contactId
        payment_map = {}
        if payments:
            for p in payments:
                cid = p.get("contactId")
                if cid:
                    val = float(p.get("totalAmount", p.get("amount", 0)))
                    payment_map[cid] = payment_map.get(cid, 0) + val

        # Helper for country from phone
        def get_country_from_phone(phone):
            if not phone: return "Other"
            p = "".join(filter(str.isdigit, str(phone)))
            if p.startswith("61"): return "Australia"
            if p.startswith("91"): return "India"
            if p.startswith("977"): return "Nepal"
            if p.startswith("92"): return "Pakistan"
            if p.startswith("880"): return "Bangladesh"
            if p.startswith("94"): return "Sri Lanka"
            if p.startswith("64"): return "New Zealand"
            if p.startswith("44"): return "UK"
            if p.startswith("1"): return "USA/Canada"
            if p.startswith("971"): return "UAE"
            if p.startswith("234"): return "Nigeria"
            if p.startswith("60"): return "Malaysia"
            if p.startswith("65"): return "Singapore"
            if p.startswith("27"): return "South Africa"
            if p.startswith("63"): return "Philippines"
            return "Other"

        # Now process stats per consultant
        consultant_results = []
        max_daily = 14
        total_capacity = max_daily * working_days

        for cal_id, name in CONSULTANTS.items():
            # Filter events for this consultant
            cal_events = [e for e in all_events if e.get("calendarId") == cal_id]
            
            # GHL V2 Statuses: confirmed, showed, noshow, cancelled, booked, new
            confirmed = sum(1 for e in cal_events if e.get("appointmentStatus", "").lower() in ["confirmed"])
            show = sum(1 for e in cal_events if e.get("appointmentStatus", "").lower() in ["showed", "show"])
            no_show = sum(1 for e in cal_events if e.get("appointmentStatus", "").lower() in ["noshow", "no-show", "no show"])
            unconfirmed = sum(1 for e in cal_events if e.get("appointmentStatus", "").lower() in ["new", "unconfirmed", "booked"])
            
            # Map countries and sum payments
            unique_cids = list(set(e.get("contactId") for e in cal_events if e.get("contactId")))
            
            # Sum from global transactions (payment_map)
            total_paid = sum(payment_map.get(cid, 0) for cid in unique_cids)
            
            # ALSO Sum directly from appointment payment data if available
            for e in cal_events:
                pd = e.get("paymentDetails", e.get("payment", {}))
                if not pd or not isinstance(pd, dict):
                    pd = e.get("meta", {}).get("payment", {})
                
                if isinstance(pd, dict):
                    apt_paid = pd.get("amountPaid") or pd.get("amount_paid") or pd.get("totalAmount") or pd.get("amount") or 0
                    try:
                        total_paid += float(apt_paid)
                    except: pass

            countries = set()
            for cid in unique_cids:
                contact = contact_map.get(cid, {})
                phone = contact.get("phone")
                countries.add(get_country_from_phone(phone))
            
            country_list = [c for c in countries if c != "Other"]
            final_country = ", ".join(sorted(country_list)) if country_list else "Other"

            consultant_results.append({
                "consultant_name": name,
                "calendar_id": cal_id,
                "total_appointments": len(cal_events),
                "amount_paid": total_paid,
                "confirmed": confirmed,
                "show": show,
                "no_show": no_show,
                "unconfirmed": unconfirmed,
                "country": final_country,
                "busy_slots": len(cal_events),
                "empty_spaces": max(0, total_capacity - len(cal_events)),
                "max_capacity": total_capacity,
                "events": cal_events
            })
        
        return consultant_results

    async def fetch_consultant_pulse(self, opportunities: List[Dict], contacts: List[Dict] = None, payments: List[Dict] = None) -> Dict[str, List[Dict]]:
        """Fetch Today and Weekly metrics for scoreboard with independent range-aware lookups (Sydney Time)"""
        tz = pytz.timezone('Australia/Sydney')
        today_dt = datetime.now(tz).date()
        
        # Today
        today_str = today_dt.strftime('%Y-%m-%d')
        
        # Weekly (Rolling Last 7 Days as per user request)
        ws = today_dt - timedelta(days=6)
        we = today_dt
        week_start_str = ws.strftime('%Y-%m-%d')
        week_end_str = we.strftime('%Y-%m-%d')
        
        print(f"\n[GHL DEBUG] CONSULTANT PULSE CALCULATION")
        print(f"--- Today: {today_str}")
        print(f"--- Weekly Rolling (7D): {week_start_str} to {week_end_str}")
        
        # For a true pulse check, fetch payments for the current week period
        pulse_payments = await self.fetch_payments(week_start_str, today_str)
        
        # 1. Fetch Today
        today_res = await self.fetch_consultant_metrics(
            start_date=today_str, end_date=today_str, 
            opportunities=opportunities, contacts=contacts, payments=pulse_payments,
            working_days=1
        )
        for dr in today_res: dr['Type'] = 'Today'
        
        # 2. Fetch Weekly (Last 7 Rolling Days)
        weekly_res = await self.fetch_consultant_metrics(
            start_date=week_start_str, end_date=week_end_str,
            opportunities=opportunities, contacts=contacts, payments=pulse_payments,
            working_days=7
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
        # payments and contacts are optional for basic opp functionality
        try:
            results = await asyncio.gather(
                self.fetch_all_contacts(),
                self.fetch_all_opportunities(),
                self.fetch_pipelines(),
                self.fetch_users(),
                self.fetch_payments(start_date, end_date),
                return_exceptions=True
            )
            
            contacts_raw = results[0] if not isinstance(results[0], Exception) else []
            opportunities_raw = results[1] if not isinstance(results[1], Exception) else []
            pipelines = results[2] if not isinstance(results[2], Exception) else []
            users = results[3] if not isinstance(results[3], Exception) else []
            payments = results[4] if not isinstance(results[4], Exception) else []
            
            if isinstance(results[1], Exception):
                print(f"GHL Opportunities Fetch Error: {results[1]}")
        except Exception as e:
            print(f"GHL Global Gather Error: {e}")
            contacts_raw, opportunities_raw, pipelines, users, payments = [], [], [], [], []
        
        # Merge opportunities so we have names/values for metrics
        merged_opps = merge_opportunity_data(opportunities_raw, pipelines, users, contacts_raw)
        
        # Now fetch consultant pulse (Today/Weekly)
        consultant_pulse = await self.fetch_consultant_pulse(opportunities=merged_opps, contacts=contacts_raw, payments=payments)
        
        # appointments for the original range
        appointments = await self.fetch_all_appointments(start_date, end_date)
        
        return {
            "contacts": contacts_raw,
            "opportunities": merged_opps, 
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
