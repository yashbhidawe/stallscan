import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
from urllib.parse import quote
from config.settings import settings
from models.schemas import PlacesData

# Import the email finder service
from .email_finder_service import EmailFinderService

class GooglePlacesService:
    def __init__(self):
        self.api_key = settings.google_places_api_key
        self.base_url = "https://maps.googleapis.com/maps/api/place"
        self.session: Optional[aiohttp.ClientSession] = None
        self.email_finder = EmailFinderService()
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        await self.email_finder.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
        await self.email_finder.__aexit__(exc_type, exc_val, exc_tb)
    
    async def _make_request(self, url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make HTTP request to Google Places API."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            params['key'] = self.api_key
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"❌ Places API error {response.status}: {await response.text()}")
                    return None
        except Exception as e:
            print(f"❌ Places API request failed: {e}")
            return None
    
    async def search_company(self, company_name: str, location: Optional[str] = None, include_email: bool = True) -> Optional[PlacesData]:
        """
        Search for a company using Google Places Text Search API.
        """
        if not company_name or not company_name.strip():
            return None
        
        # Build search query
        query = company_name.strip()
        if location:
            query = f"{query} {location}"
        
        url = f"{self.base_url}/textsearch/json"
        params = {
            'query': query,
            'type': 'establishment',
            'fields': 'place_id,name,formatted_address,geometry,rating,user_ratings_total,website,formatted_phone_number,business_status,types'
        }
        
        result = await self._make_request(url, params)
        if not result or result.get('status') != 'OK':
            return None
        
        candidates = result.get('results', [])
        if not candidates:
            return None
        
        # Get the best match (first result is usually most relevant)
        best_match = candidates[0]
        
        # Get detailed information
        return await self.get_place_details(best_match.get('place_id'), include_email=include_email)
    
    async def get_place_details(self, place_id: str, include_email: bool = True) -> Optional[PlacesData]:
        """
        Get detailed information about a place using Place Details API.
        """
        if not place_id:
            return None
        
        url = f"{self.base_url}/details/json"
        params = {
            'place_id': place_id,
            'fields': 'place_id,name,formatted_address,geometry,rating,user_ratings_total,website,formatted_phone_number,business_status,types,opening_hours'
        }
        
        result = await self._make_request(url, params)
        if not result or result.get('status') != 'OK':
            return None
        
        place_data = result.get('result', {})
        
        # Extract email using the email finder service
        email = None
        website = place_data.get('website')
        company_name = place_data.get('name')
        
        if include_email and website and company_name:
            try:
                email = await self.email_finder.find_company_email(company_name, website)
                if email:
                    print(f"✅ Found email for {company_name}: {email}")
                else:
                    print(f"ℹ️ No email found for {company_name}")
            except Exception as e:
                print(f"❌ Email finding failed for {company_name}: {e}")
        
        # Extract and format the data
        return PlacesData(
            place_id=place_data.get('place_id'),
            name=place_data.get('name'),
            website=website,
            phone=place_data.get('formatted_phone_number'),
            address=place_data.get('formatted_address'),
            email=email
        )
    
    async def enrich_companies_batch(self, company_names: List[str], location: Optional[str] = None, 
                                   max_concurrent: int = 3, include_email: bool = True) -> Dict[str, Optional[PlacesData]]:
        """
        Enrich multiple companies concurrently with rate limiting.
        Reduced default concurrency to be more respectful to websites.
        """
        if not company_names:
            return {}
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enrich_single(company_name: str) -> tuple[str, Optional[PlacesData]]:
            async with semaphore:
                try:
                    places_data = await self.search_company(company_name, location, include_email=include_email)
                    # Add delay to respect rate limits (both Google Places and target websites)
                    await asyncio.sleep(0.2)
                    return company_name, places_data
                except Exception as e:
                    print(f"❌ Error enriching {company_name}: {e}")
                    return company_name, None
        
        # Create tasks for concurrent execution
        tasks = [enrich_single(company) for company in company_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert results to dictionary
        enrichment_data = {}
        for result in results:
            if isinstance(result, tuple):
                company_name, places_data = result
                enrichment_data[company_name] = places_data
            else:
                print(f"❌ Task failed: {result}")
        
        return enrichment_data
    
    async def find_emails_only(self, companies_with_websites: List[Dict[str, str]], max_concurrent: int = 3) -> Dict[str, Optional[str]]:
        """
        Find emails for companies that already have website information.
        companies_with_websites: List of dicts with 'name' and 'website' keys
        """
        return await self.email_finder.find_emails_batch(companies_with_websites, max_concurrent)