import asyncio
import aiohttp
import re
from typing import Optional, List, Set, Dict, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging

class EmailFinderService:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.email_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
        ]
        
        # Common email prefixes to try
        self.common_prefixes = [
            'info', 'contact', 'hello', 'support', 'admin', 'office',
            'sales', 'enquiry', 'inquiry', 'general', 'main'
        ]
        
        # Pages likely to contain contact information
        self.contact_pages = [
            '/contact', '/contact-us', '/about', '/about-us', 
            '/team', '/staff', '/leadership', '/management',
            '/imprint', '/impressum', '/legal'
        ]
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def extract_emails_from_text(self, text: str) -> Set[str]:
        """Extract email addresses from text using regex patterns."""
        emails = set()
        for pattern in self.email_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    emails.add(match[0].lower())
                else:
                    emails.add(match.lower())
        return emails
    
    def get_domain_from_url(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower().replace('www.', '')
        except:
            return None
    
    def filter_relevant_emails(self, emails: Set[str], domain: str, company_name: str) -> List[str]:
        """Filter emails to find most relevant ones for the company."""
        if not emails:
            return []
        
        relevant_emails = []
        company_words = set(company_name.lower().split())
        
        for email in emails:
            email_domain = email.split('@')[1] if '@' in email else ''
            email_local = email.split('@')[0] if '@' in email else ''
            
            # Skip obviously irrelevant emails
            skip_patterns = ['noreply', 'no-reply', 'donotreply', 'unsubscribe']
            if any(pattern in email_local.lower() for pattern in skip_patterns):
                continue
            
            # Prioritize emails from same domain
            if domain and domain in email_domain:
                # Check if it's a general contact email
                if any(prefix in email_local.lower() for prefix in self.common_prefixes):
                    relevant_emails.insert(0, email)  # High priority
                else:
                    relevant_emails.append(email)
            
            # Also consider emails that might contain company name
            elif any(word in email_local.lower() for word in company_words if len(word) > 3):
                relevant_emails.append(email)
        
        return relevant_emails
    
    async def scrape_page_for_emails(self, url: str) -> Set[str]:
        """Scrape a single page for email addresses."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return set()
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text()
                
                # Also check href attributes for mailto links
                mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.I))
                for link in mailto_links:
                    href = link.get('href', '')
                    if href.startswith('mailto:'):
                        text += ' ' + href
                
                return self.extract_emails_from_text(text)
                
        except Exception as e:
            logging.debug(f"Error scraping {url}: {e}")
            return set()
    
    async def find_company_email(self, company_name: str, website: str) -> Optional[str]:
        """
        Find company email using multiple strategies:
        1. Scrape main website
        2. Check common contact pages
        3. Try common email patterns
        """
        if not website or not company_name:
            return None
        
        # Ensure website has protocol
        if not website.startswith(('http://', 'https://')):
            website = 'https://' + website
        
        domain = self.get_domain_from_url(website)
        if not domain:
            return None
        
        all_emails = set()
        
        # Strategy 1: Scrape main website
        main_emails = await self.scrape_page_for_emails(website)
        all_emails.update(main_emails)
        
        # Strategy 2: Check common contact pages
        contact_urls = [urljoin(website, page) for page in self.contact_pages]
        contact_tasks = [self.scrape_page_for_emails(url) for url in contact_urls]
        
        try:
            contact_results = await asyncio.gather(*contact_tasks, return_exceptions=True)
            for result in contact_results:
                if isinstance(result, set):
                    all_emails.update(result)
        except Exception as e:
            logging.debug(f"Error in contact page scraping: {e}")
        
        # Filter and prioritize emails
        relevant_emails = self.filter_relevant_emails(all_emails, domain, company_name)
        
        # Strategy 3: If no emails found, try common patterns
        if not relevant_emails:
            common_emails = [f"{prefix}@{domain}" for prefix in self.common_prefixes]
            # We could verify these exist, but that requires SMTP checking
            # For now, return the most likely one
            if 'info@' + domain not in [email for email in all_emails]:
                relevant_emails = [f"info@{domain}"]
        
        return relevant_emails[0] if relevant_emails else None
    
    async def verify_email_exists(self, email: str) -> bool:
        """
        Basic email verification (check domain MX record).
        Note: Full SMTP verification might be blocked by many servers.
        """
        try:
            import dns.resolver
            domain = email.split('@')[1]
            mx_records = dns.resolver.resolve(domain, 'MX')
            return len(mx_records) > 0
        except:
            # If DNS resolution fails, assume email might exist
            return True
    
    async def find_emails_batch(self, companies_data: List[Dict[str, str]], max_concurrent: int = 3) -> Dict[str, Optional[str]]:
        """
        Find emails for multiple companies concurrently.
        companies_data: List of dicts with 'name' and 'website' keys
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def find_single_email(company_data: Dict[str, str]) -> tuple[str, Optional[str]]:
            async with semaphore:
                try:
                    company_name = company_data.get('name', '')
                    website = company_data.get('website', '')
                    email = await self.find_company_email(company_name, website)
                    await asyncio.sleep(0.5)  # Be respectful with requests
                    return company_name, email
                except Exception as e:
                    logging.error(f"Error finding email for {company_data.get('name', 'Unknown')}: {e}")
                    return company_data.get('name', ''), None
        
        tasks = [find_single_email(company_data) for company_data in companies_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        email_results = {}
        for result in results:
            if isinstance(result, tuple):
                company_name, email = result
                email_results[company_name] = email
            else:
                logging.error(f"Task failed: {result}")
        
        return email_results