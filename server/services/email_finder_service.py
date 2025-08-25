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
        
        # Enhanced email prefixes with priority scoring
        self.common_prefixes = [
            # High priority - general business contacts
            'info', 'contact', 'hello', 'general', 'main', 'office',
            # Medium priority - department specific
            'sales', 'business', 'partnerships', 'marketing', 'pr',
            'enquiry', 'inquiry', 'support', 'service', 'customer',
            # Lower priority - but still relevant
            'admin', 'reception', 'team', 'mail'
        ]
        
        # Enhanced contact pages with better coverage
        self.contact_pages = [
            # Primary contact pages
            '/contact', '/contact-us', '/contact-form', '/get-in-touch',
            '/reach-us', '/connect', '/contactus',
            
            # About and team pages
            '/about', '/about-us', '/aboutus', '/team', '/our-team', 
            '/staff', '/people', '/leadership', '/management', '/executives',
            
            # Business pages
            '/partners', '/partnership', '/business', '/corporate',
            '/press', '/media', '/newsroom', '/investor-relations',
            
            # Footer and legal pages that often contain emails
            '/footer', '/imprint', '/impressum', '/legal', '/privacy',
            '/terms', '/sitemap'
        ]
        
        # Industry-specific contact patterns
        self.industry_contact_patterns = {
            'technology': ['tech@', 'dev@', 'engineering@', 'it@', 'digital@'],
            'healthcare': ['medical@', 'clinic@', 'health@', 'patient@', 'care@'],
            'manufacturing': ['production@', 'factory@', 'operations@', 'quality@'],
            'finance': ['finance@', 'accounting@', 'investment@', 'advisor@'],
            'retail': ['store@', 'shop@', 'customer@', 'orders@', 'retail@'],
            'education': ['admissions@', 'academic@', 'student@', 'registrar@'],
            'consulting': ['consulting@', 'advisory@', 'solutions@', 'strategy@']
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),  # Increased timeout for better coverage
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def extract_emails_from_text(self, text: str) -> Set[str]:
        """Extract email addresses from text using enhanced regex patterns."""
        emails = set()
        
        # Enhanced patterns for better email detection
        enhanced_patterns = [
            # Standard email pattern
            r'\b[A-Za-z0-9]([A-Za-z0-9._%+-]*[A-Za-z0-9])?@[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}\b',
            # Mailto links
            r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})',
            # Email in quotes or parentheses  
            r'["\']([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})["\']',
            # Email with surrounding text indicators
            r'(?:email|e-mail|contact|write|send)[\s:]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})',
            # Email in JavaScript or hidden in HTML
            r'([A-Za-z0-9._%+-]+)(?:\s*\[at\]\s*|\s*@\s*)([A-Za-z0-9.-]+)(?:\s*\[dot\]\s*|\s*\.\s*)([A-Za-z]{2,})'
        ]
        
        for pattern in enhanced_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 3:  # Pattern with [at] and [dot]
                        email = f"{match[0]}@{match[1]}.{match[2]}"
                    else:
                        email = match[0] if match[0] else (match[1] if len(match) > 1 else '')
                else:
                    email = match
                
                if email and '@' in email and '.' in email:
                    emails.add(email.lower().strip())
        
        return emails
    
    def get_domain_from_url(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower().replace('www.', '')
        except:
            return None
    
    def filter_relevant_emails(self, emails: Set[str], domain: str, company_name: str, industry_hint: Optional[str] = None) -> List[str]:
        """Enhanced email filtering with industry context and better prioritization."""
        if not emails:
            return []
        
        relevant_emails = []
        company_words = set(re.findall(r'\b\w{3,}\b', company_name.lower()))
        
        # Create scoring system for email relevance
        email_scores = {}
        
        for email in emails:
            if '@' not in email:
                continue
                
            email_local, email_domain = email.split('@', 1)
            email_local = email_local.lower()
            email_domain = email_domain.lower()
            
            # Skip obviously irrelevant emails
            skip_patterns = [
                'noreply', 'no-reply', 'donotreply', 'unsubscribe', 'bounce',
                'postmaster', 'mailer-daemon', 'abuse', 'spam'
            ]
            if any(pattern in email_local for pattern in skip_patterns):
                continue
            
            score = 0
            
            # Domain relevance scoring
            if domain and domain in email_domain:
                score += 50  # Same domain gets high base score
            elif any(word in email_domain for word in company_words if len(word) > 3):
                score += 30  # Domain contains company words
            
            # Email prefix scoring
            high_priority_prefixes = ['info', 'contact', 'hello', 'general', 'main']
            medium_priority_prefixes = ['sales', 'business', 'marketing', 'support']
            
            if any(prefix == email_local for prefix in high_priority_prefixes):
                score += 40
            elif any(prefix in email_local for prefix in high_priority_prefixes):
                score += 25
            elif any(prefix in email_local for prefix in medium_priority_prefixes):
                score += 15
            
            # Industry-specific scoring
            if industry_hint and industry_hint.lower() in self.industry_contact_patterns:
                industry_patterns = self.industry_contact_patterns[industry_hint.lower()]
                for pattern in industry_patterns:
                    if pattern.replace('@', '') in email_local:
                        score += 20
                        break
            
            # Company name relevance
            if any(word in email_local for word in company_words if len(word) > 3):
                score += 15
            
            # Penalize very generic emails from different domains
            if not domain or domain not in email_domain:
                generic_patterns = ['admin', 'webmaster', 'root', 'test']
                if any(pattern in email_local for pattern in generic_patterns):
                    score -= 20
            
            email_scores[email] = score
        
        # Sort by score and return top emails
        sorted_emails = sorted(email_scores.items(), key=lambda x: x[1], reverse=True)
        relevant_emails = [email for email, score in sorted_emails if score > 0]
        
        return relevant_emails[:5]  # Return top 5 most relevant emails
    
    async def scrape_page_for_emails(self, url: str) -> Set[str]:
        """Enhanced page scraping with better email detection."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return set()
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                all_emails = set()
                
                # Strategy 1: Extract from mailto links first (highest accuracy)
                mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.I))
                for link in mailto_links:
                    href = link.get('href', '').replace('mailto:', '')
                    if '@' in href:
                        # Clean up the email (remove subject, cc, etc.)
                        email = href.split('?')[0].split('&')[0]
                        all_emails.add(email.lower())
                
                # Strategy 2: Look in specific elements that commonly contain emails
                contact_selectors = [
                    # Common contact section classes/IDs
                    '[class*="contact"]', '[id*="contact"]',
                    '[class*="footer"]', '[id*="footer"]',
                    '[class*="email"]', '[id*="email"]',
                    
                    # Structured data
                    '[itemtype*="Organization"]', '[itemtype*="LocalBusiness"]',
                    
                    # Common contact elements
                    'address', '.contact-info', '.contact-details',
                    '.company-info', '.business-info'
                ]
                
                contact_text = ""
                for selector in contact_selectors:
                    elements = soup.select(selector)
                    for element in elements:
                        contact_text += " " + element.get_text(separator=' ')
                
                # Strategy 3: Get all text but prioritize contact sections
                for script in soup(["script", "style"]):
                    script.decompose()
                
                page_text = soup.get_text(separator=' ')
                
                # Combine contact text (higher weight) with page text
                combined_text = contact_text + " " + page_text
                
                # Extract emails from combined text
                extracted_emails = self.extract_emails_from_text(combined_text)
                all_emails.update(extracted_emails)
                
                return all_emails
                
        except Exception as e:
            logging.debug(f"Error scraping {url}: {e}")
            return set()
    
    async def find_company_email(self, company_name: str, website: str, industry_hint: Optional[str] = None) -> Optional[str]:
        """
        Enhanced email finding with industry context and better search strategy.
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
        
        # Strategy 1: Scrape main website with enhanced detection
        print(f"  📧 Searching main site: {website}")
        main_emails = await self.scrape_page_for_emails(website)
        all_emails.update(main_emails)
        
        # Strategy 2: Check contact pages with prioritized list
        priority_contact_pages = ['/contact', '/contact-us', '/about', '/team']
        standard_contact_pages = [page for page in self.contact_pages if page not in priority_contact_pages]
        
        # Check priority pages first
        for page in priority_contact_pages:
            contact_url = urljoin(website, page)
            print(f"  📧 Checking priority page: {page}")
            page_emails = await self.scrape_page_for_emails(contact_url)
            all_emails.update(page_emails)
            await asyncio.sleep(0.3)  # Small delay between requests
        
        # If we found emails from priority pages, use them
        if all_emails:
            relevant_emails = self.filter_relevant_emails(all_emails, domain, company_name, industry_hint)
            if relevant_emails:
                print(f"  ✅ Found email from priority pages: {relevant_emails[0]}")
                return relevant_emails[0]
        
        # Strategy 3: Check additional contact pages if needed
        for page in standard_contact_pages[:6]:  # Limit to avoid too many requests
            contact_url = urljoin(website, page)
            page_emails = await self.scrape_page_for_emails(contact_url)
            all_emails.update(page_emails)
            await asyncio.sleep(0.3)
        
        # Strategy 4: Filter and prioritize all found emails
        relevant_emails = self.filter_relevant_emails(all_emails, domain, company_name, industry_hint)
        
        # Strategy 5: Enhanced fallback patterns with industry context
        if not relevant_emails:
            print(f"  🔄 Fallback to common patterns for {domain}")
          
            
            # Return the most promising fallback
            return "Not Found"
        
        result_email = relevant_emails[0]
        print(f"  ✅ Found email: {result_email}")
        return result_email
    
    async def verify_email_exists(self, email: str) -> bool:
        """Enhanced email verification with MX record checking."""
        try:
            import dns.resolver
            domain = email.split('@')[1]
            
            # Check MX records
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                if len(mx_records) > 0:
                    return True
            except:
                pass
            
            # Fallback: Check if domain has A record
            try:
                a_records = dns.resolver.resolve(domain, 'A')
                return len(a_records) > 0
            except:
                pass
                
        except:
            pass
        
        # If DNS resolution fails, assume email might exist
        return True
    
    async def find_emails_batch(self, companies_data: List[Dict[str, str]], max_concurrent: int = 3) -> Dict[str, Optional[str]]:
        """
        Enhanced batch email finding with industry context support.
        companies_data: List of dicts with 'name', 'website', and optional 'industry' keys
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def find_single_email(company_data: Dict[str, str]) -> tuple[str, Optional[str]]:
            async with semaphore:
                try:
                    company_name = company_data.get('name', '')
                    website = company_data.get('website', '')
                    industry_hint = company_data.get('industry')
                    
                    print(f"🔍 Finding email for: {company_name}")
                    email = await self.find_company_email(company_name, website, industry_hint)
                    
                    if email:
                        print(f"✅ Email found for {company_name}: {email}")
                    else:
                        print(f"❌ No email found for {company_name}")
                    
                    await asyncio.sleep(0.8)  # Respectful delay between companies
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