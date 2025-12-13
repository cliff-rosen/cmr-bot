import requests
import xml.etree.ElementTree as ET
import urllib.parse
import logging
import time
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

"""
DOCS
https://www.ncbi.nlm.nih.gov/books/NBK25501/
https://www.ncbi.nlm.nih.gov/books/NBK25499/

SAMPLE CALLS
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=%28%28melanocortin%29%20OR%20%28natriuretic%29%20OR%20%28Dry%20eye%29%20OR%20%28Ulcerative%20colitis%29%20OR%20%28Crohn%E2%80%99s%20disease%29%20OR%20%28Retinopathy%29%20OR%20%28Retinal%20disease%29%29AND%20%28%28%222023/11/01%3E%22%5BDate%20-%20Completion%5D%20%3A%20%222023/11/30%22%5BDate%20-%20Completion%5D%29%29&retmax=10000&retmode=json
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=melanocortin&retmax=10000&retmode=json
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=38004229&retmode=xml

"""
PUBMED_API_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_API_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _get_pubmed_max_results() -> int:
    """Helper function to get PubMed max results from settings."""
    from config.settings import settings
    return settings.PUBMED_MAX_RESULTS_PER_CALL

class PubMedArticle():
    """
    PubmedArticle
        MedlineCitation
            PMID
            Article (PubModel)
                Journal
                    JournalIssue (CitedMedium)
                        Volume
                        Issue
                        PubDate
                    Title
                ArticleTitle
                Pagination
                Abstract
                AuthorList

    """

    @classmethod
    def from_xml(cls, article_xml: bytes) -> 'PubMedArticle':
        pubmed_article_node = ET.fromstring(article_xml)
        medline_citation_node = pubmed_article_node.find('.//MedlineCitation')

        PMID_node = medline_citation_node.find(".//PMID")
        article_node = medline_citation_node.find('.//Article')
        date_completed_node = medline_citation_node.find(".//DateCompleted")
        date_revised_node = medline_citation_node.find(".//DateRevised")
        # ArticleDate can be in Article or directly in MedlineCitation
        article_date_node = None
        if article_node is not None:
            article_date_node = article_node.find(".//ArticleDate")
        if article_date_node is None:
            article_date_node = medline_citation_node.find(".//ArticleDate")
        # Entry date is in PubmedData/History/PubMedPubDate with PubStatus="entrez"
        pubmed_data_node = pubmed_article_node.find('.//PubmedData')
        entry_date_node = None
        if pubmed_data_node is not None:
            history_node = pubmed_data_node.find('.//History')
            if history_node is not None:
                entry_date_node = history_node.find('.//PubMedPubDate[@PubStatus="entrez"]')

        journal_node = article_node.find('.//Journal')
        journal_issue_node = journal_node.find(".//JournalIssue")
        journal_title_node = journal_node.find(".//Title")
        volume_node = journal_issue_node.find(".//Volume")
        issue_node = journal_issue_node.find(".//Issue")
        pubdate_node = journal_issue_node.find(".//PubDate")
        year_node = pubdate_node.find(".//Year")

        article_title_node = medline_citation_node.find(".//ArticleTitle")
        pagination_node = medline_citation_node.find('.//Pagination/MedlinePgn')
        abstract_node = medline_citation_node.find(".//Abstract")
        author_list_node = medline_citation_node.find('.//AuthorList')

        PMID = ""
        title = ""
        journal = ""
        medium = ""
        year = ""
        month = ""
        day = ""
        volume = ""
        issue = ""
        pages = ""           
        date_completed = ""
        date_revised = ""
        article_date = ""
        entry_date = ""
        pub_date = ""

        if PMID_node is not None:
            PMID = PMID_node.text
        logger.debug(f"Processing article PMID: {PMID}")
        if article_title_node is not None:
            title = ''.join(article_title_node.itertext())
        if journal_title_node is not None:
            journal = journal_title_node.text
        if journal_issue_node is not None:
            medium = journal_issue_node.attrib['CitedMedium']
        if year_node is not None:
            year = year_node.text
        if volume_node is not None:
            volume = volume_node.text
        if issue_node is not None:
            issue = issue_node.text
        if pagination_node is not None:
            pages = pagination_node.text
        date_completed = cls._get_date_from_node(date_completed_node)
        date_revised = cls._get_date_from_node(date_revised_node)
        article_date = cls._get_date_from_node(article_date_node)
        entry_date = cls._get_date_from_node(entry_date_node)
        
        # Debug logging
        logger.debug(f"PMID {PMID} - Date extraction:")
        logger.debug(f"  date_completed: {date_completed}")
        logger.debug(f"  date_revised: {date_revised}")
        logger.debug(f"  article_date: {article_date}")
        logger.debug(f"  entry_date: {entry_date}")
        # Get pub_date from year/month/day already extracted
        if year:
            pub_date = year
            if pubdate_node is not None:
                month_node = pubdate_node.find(".//Month")
                day_node = pubdate_node.find(".//Day")
                if month_node is not None:
                    month = month_node.text
                    pub_date += f"-{month.zfill(2)}"
                    if day_node is not None:
                        day = day_node.text
                        pub_date += f"-{day.zfill(2)}"
                else:
                    pub_date += "-01-01"  # Default to Jan 1 if no month

        MAX_AUTHOR_COUNT = 3
        author_list = []
        author_node_list = []
        if author_list_node is not None:
            author_node_list = author_list_node.findall('.//Author')
        for author_node in author_node_list[0:3]:
            last_name_node = author_node.find('.//LastName')
            if  last_name_node is not None:
                last_name = last_name_node.text
                initials_node = author_node.find('.//Initials')
                if initials_node is not None:
                    initials = initials_node.text
                else:
                    initials = ""
                author_list.append(f"{last_name} {initials}")
        authors = ', '.join(author_list)
        if len(author_node_list) > MAX_AUTHOR_COUNT:
            authors += ', et al'

        abstract = ""
        if abstract_node is not None:
            abstract_texts = abstract_node.findall('.//AbstractText')
            if abstract_texts is not None and len(abstract_texts) > 0:
                for abstract_text in abstract_texts:
                    abstract += ''.join(abstract_text.itertext())

        # Extract ArticleIdList for PMC ID and DOI
        pmc_id = ""
        doi = ""
        if pubmed_data_node is not None:
            article_id_list = pubmed_data_node.find('.//ArticleIdList')
            if article_id_list is not None:
                for article_id in article_id_list.findall('.//ArticleId'):
                    id_type = article_id.get('IdType', '')
                    if id_type == 'pmc' and article_id.text:
                        pmc_id = article_id.text
                    elif id_type == 'doi' and article_id.text:
                        doi = article_id.text

        citation = f"{authors} {title} {journal}. {year};{volume}({issue}):{pages}."

        return PubMedArticle(
                    PMID=PMID,
                    comp_date=date_completed,
                    date_revised=date_revised,
                    article_date=article_date,
                    entry_date=entry_date,
                    pub_date=pub_date,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    journal=journal,
                    medium=medium,
                    year=year,
                    volume=volume,
                    issue=issue,
                    pages=pages,
                    pmc_id=pmc_id,
                    doi=doi
                    )

    def __init__(self, **kwargs: Any) -> None:
        #print(kwargs)
        self.PMID = kwargs['PMID']
        self.comp_date = kwargs['comp_date']
        self.date_revised = kwargs.get('date_revised', '')
        self.article_date = kwargs.get('article_date', '')
        self.entry_date = kwargs.get('entry_date', '')
        self.pub_date = kwargs.get('pub_date', '')
        self.title = kwargs['title']
        self.abstract = kwargs['abstract']
        self.authors = kwargs['authors']
        self.journal = kwargs['journal']
        self.year = kwargs['year']
        self.volume = kwargs['volume']
        self.issue = kwargs['issue']
        self.pages = kwargs['pages']
        self.medium = kwargs['medium']
        self.pmc_id = kwargs.get('pmc_id', '')
        self.doi = kwargs.get('doi', '')

    def __str__(self) -> str:
        line = "===================================================\n"        
        res = "PMID: " + self.PMID + '\n' \
            + "Comp date: " + self.comp_date + '\n' \
            + "Title: " + self.title[0:80] + '\n' \
            + "Abstract: " + self.abstract[0:80] + '\n' \
            + "Authors: " + self.authors[0:80] + '\n' \
            + 'Journal: ' + self.journal[0:80] + '\n' \
            + 'Year: ' + self.year + '\n' \
            + 'Volume: ' + self.volume + '\n' \
            + 'Issue: ' + self.issue + '\n' \
            + 'Medium: ' + self.medium
        
        return line + res

    @staticmethod
    def _get_date_from_node(date_node: Optional[ET.Element]) -> str:
        if date_node is None:
            return ""
        
        year_node = date_node.find(".//Year")
        month_node = date_node.find(".//Month")
        day_node = date_node.find(".//Day")
        
        # Debug logging
        logger.debug(f"Date node tag: {date_node.tag}")
        logger.debug(f"Year node: {year_node.text if year_node is not None else 'None'}")
        logger.debug(f"Month node: {month_node.text if month_node is not None else 'None'}")
        logger.debug(f"Day node: {day_node.text if day_node is not None else 'None'}")
        
        # Year is required
        if year_node is None or year_node.text is None:
            logger.debug("No year found, returning empty string")
            return ""
        
        year = year_node.text
        month = month_node.text if month_node is not None and month_node.text else "01"
        day = day_node.text if day_node is not None and day_node.text else "01"
        
        # Ensure month and day are zero-padded
        month = month.zfill(2)
        day = day.zfill(2)
        
        result = f"{year}-{month}-{day}"
        logger.debug(f"Returning date: {result}")
        return result


def get_citation_from_article(article: PubMedArticle) -> str:
    authors = article.authors
    title = article.title
    journal = article.journal
    year = article.year
    volume = article.volume
    issue = article.issue
    pages = article.pages
    
    return f"{authors} ({year}). {title}. {journal}, {volume}({issue}), {pages}."


def search_articles(
    query: str,
    max_results: int = 100,
    offset: int = 0,
    sort_by: str = "relevance",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date_type: Optional[str] = None
) -> tuple[List['CanonicalResearchArticle'], Dict[str, Any]]:
    """
    Module-level search function to match Google Scholar pattern.
    Creates a service instance and calls _search_articles.
    """
    service = PubMedService()
    return service.search_articles(
        query=query,
        max_results=max_results,
        offset=offset,
        sort_by=sort_by,
        start_date=start_date,
        end_date=end_date,
        date_type=date_type
    )


class PubMedService:
    """Service for interacting with PubMed via NCBI E-utilities API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the PubMed service.

        Args:
            api_key: NCBI API key. If not provided, will look in settings then env var.
        """
        if api_key:
            self.api_key = api_key
        else:
            # Try settings first, then env var
            try:
                from config.settings import settings
                self.api_key = settings.NCBI_API_KEY if settings.NCBI_API_KEY else None
            except Exception:
                self.api_key = os.getenv("NCBI_API_KEY")

        self.search_url = PUBMED_API_SEARCH_URL
        self.fetch_url = PUBMED_API_FETCH_URL

        if self.api_key:
            logger.info("Using NCBI API key for increased rate limits")
        else:
            logger.info("No NCBI API key configured - using rate-limited access (3 req/sec)")
    
    def _get_max_results_per_call(self) -> int:
        """Get the maximum number of results this provider can return per API call."""
        from config.settings import settings
        return settings.PUBMED_MAX_RESULTS_PER_CALL
    
    def get_article_ids(
        self,
        query: str,
        max_results: int = 1000,
        sort_by: str = "relevance",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        date_type: Optional[str] = None
    ) -> tuple[List[str], int]:
        """
        Get just the PubMed IDs from a search query (fast - no article fetching).

        Returns:
            Tuple of (list of PMIDs, total count)
        """
        return self._get_article_ids(
            search_term=query,
            max_results=max_results,
            sort_by=sort_by,
            start_date=start_date,
            end_date=end_date,
            date_type=date_type
        )

    def search_articles(
        self,
        query: str,
        max_results: int = 100,
        offset: int = 0,
        sort_by: str = "relevance",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        date_type: Optional[str] = None
    ) -> tuple[List['CanonicalResearchArticle'], Dict[str, Any]]:
        """
        Search PubMed articles using the class method.
        """
        from schemas.base import CanonicalResearchArticle

        logger.info(f"PubMed search: query='{query}', max_results={max_results}, offset={offset}")

        # Get article IDs with total count
        article_ids, total_count = self._get_article_ids(
            search_term=query,
            max_results=offset + max_results,  # Get enough IDs for pagination
            sort_by=sort_by,
            start_date=start_date,
            end_date=end_date,
            date_type=date_type
        )

        logger.info(f"Found {total_count} total results, retrieved {len(article_ids)} IDs")

        # Apply pagination to IDs
        paginated_ids = article_ids[offset:offset + max_results]

        if not paginated_ids:
            return [], {
                "total_results": total_count,
                "offset": offset,
                "returned": 0
            }

        # Get full article data for the current page
        logger.info(f"Fetching article data for {len(paginated_ids)} articles")
        articles = self._get_articles_from_ids(paginated_ids)
        logger.info(f"Retrieved {len(articles)} articles")

        # Convert to canonical format
        canonical_articles = []
        for i, article in enumerate(articles):
            try:
                # Parse authors list
                authors_list = []
                if article.authors:
                    # Split by comma, handle "et al" suffix
                    authors_str = article.authors.replace(", et al", "")
                    authors_list = [a.strip() for a in authors_str.split(", ") if a.strip()]

                # Create CanonicalResearchArticle directly
                research_article = CanonicalResearchArticle(
                    pmid=article.PMID,
                    doi=article.doi if hasattr(article, 'doi') else None,
                    title=article.title or "[No title available]",
                    abstract=article.abstract or None,
                    authors=authors_list if authors_list else None,
                    journal=article.journal or None,
                    publication_date=article.pub_date if article.pub_date else None,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{article.PMID}/" if article.PMID else None,
                    source="pubmed",
                    metadata={
                        "volume": article.volume,
                        "issue": article.issue,
                        "pages": article.pages,
                        "medium": article.medium,
                        "comp_date": article.comp_date,
                        "date_revised": article.date_revised,
                        "article_date": article.article_date,
                        "entry_date": article.entry_date,
                        "pmc_id": article.pmc_id if hasattr(article, 'pmc_id') else None,
                        "search_position": offset + i + 1
                    }
                )
                canonical_articles.append(research_article)

            except Exception as e:
                logger.error(f"Error converting article {getattr(article, 'PMID', 'unknown')}: {e}")
                logger.error(f"Article data - Title: {getattr(article, 'title', 'None')}, Abstract: {getattr(article, 'abstract', 'None')[:100] if getattr(article, 'abstract', None) else 'None'}, Journal: {getattr(article, 'journal', 'None')}")
                continue

        # Trim to requested max_results if we got extra
        if len(canonical_articles) > max_results:
            canonical_articles = canonical_articles[:max_results]

        metadata = {
            "total_results": total_count,
            "offset": offset,
            "returned": len(canonical_articles)
        }

        return canonical_articles, metadata
    
    def _get_date_clause(self, start_date: str, end_date: str, date_type: str = "publication") -> str:
        """Build PubMed date filter clause based on date type."""
        # Map date types to PubMed E-utilities search field tags
        date_field_map = {
            "completion": "DCOM",  # Date Completed
            "publication": "DP",   # Date of Publication 
            "entry": "EDAT",       # Entry Date (formerly Entrez Date)
            "revised": "LR"        # Date Last Revised
        }
        
        field = date_field_map.get(date_type, "DP")
        clause = f'AND (("{start_date}"[{field}] : "{end_date}"[{field}]))'
        return clause
    
    def _get_article_ids(
        self,
        search_term: str, 
        max_results: int = 100, 
        sort_by: str = "relevance",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        date_type: str = "publication"
    ) -> tuple[List[str], int]:
        """Search PubMed for article IDs with optional date filtering."""
        url = self.search_url
        
        # Build search term with optional date clause
        if start_date and end_date:
            full_term = f'({search_term}){self._get_date_clause(start_date, end_date, date_type)}'
        else:
            full_term = search_term
        
        params = {
            'db': 'pubmed',
            'term': full_term,
            'retmax': min(max_results, self._get_max_results_per_call()),
            'retmode': 'json'
        }
        
        # Map unified sort values to PubMed API sort values
        sort_mapping = {
            'relevance': None,  # Default, don't need to specify
            'date': 'pub_date'  # Sort by publication date
        }
        
        pubmed_sort = sort_mapping.get(sort_by)
        if pubmed_sort:
            params['sort'] = pubmed_sort
        
        headers = {
            'User-Agent': 'JamBot/1.0 (Research Assistant; Contact: admin@example.com)'
        }
        
        # Add NCBI API key if available
        if self.api_key:
            params['api_key'] = self.api_key
        
        logger.info(f'Retrieving article IDs for query: {full_term}')
        logger.debug(f'Parameters: {params}')

        # Check if the URL is too long (PubMed has a limit of about 2000-3000 characters)
        # Build the full URL to check its length
        from urllib.parse import urlencode
        full_url = f"{url}?{urlencode(params)}"
        if len(full_url) > 2000:
            logger.error(f"URL too long ({len(full_url)} characters): Query is too complex")
            raise ValueError(f"Search query is too long ({len(full_url)} characters). PubMed has a URL length limit. Please simplify your search by reducing the number of terms.")

        # Retry logic with exponential backoff for 429 and connection errors
        max_retries = 5
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=30)

                # Check for rate limiting
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.warning(f"Rate limited by NCBI (429), waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Rate limit exceeded after {max_retries} retries")
                        response.raise_for_status()

                response.raise_for_status()

                content_type = response.headers.get('content-type', '')
                if 'application/json' not in content_type:
                    logger.error(f"Expected JSON but got content-type: {content_type}")
                    raise Exception(f"PubMed API returned non-JSON response. Content-Type: {content_type}")

                if not response.text:
                    logger.error("PubMed API returned empty response body")
                    raise Exception("PubMed API returned empty response")

                content = response.json()

                if 'esearchresult' not in content:
                    raise Exception("Invalid response format from PubMed API")

                count = int(content['esearchresult']['count'])
                ids = content['esearchresult']['idlist']

                logger.info(f"Found {count} articles, returning {len(ids)} IDs")
                return ids, count

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP error in PubMed search: {e}", exc_info=True)
                    raise Exception(f"PubMed API request failed: {str(e)}")

        # Should not reach here, but just in case
        raise Exception("PubMed search failed after all retries")
    
    def get_articles_from_ids(self, ids: List[str]) -> List[PubMedArticle]:
        """
        Fetch full article data from PubMed IDs (public wrapper).

        Args:
            ids: List of PubMed IDs

        Returns:
            List of PubMedArticle objects
        """
        return self._get_articles_from_ids(ids)

    def _get_articles_from_ids(self, ids: List[str]) -> List[PubMedArticle]:
        """Fetch full article data from PubMed IDs."""
        BATCH_SIZE = 100
        # NCBI rate limit: 3 requests/sec without API key, 10/sec with key
        REQUEST_DELAY = 0.1 if self.api_key else 0.4

        articles = []
        batch_size = BATCH_SIZE
        low = 0
        high = low + batch_size

        headers = {
            'User-Agent': 'CMRBot/1.0 (Research Assistant; Contact: admin@example.com)'
        }

        while low < len(ids):
            logger.info(f"Processing articles {low} to {high}")
            id_batch = ids[low: high]
            url = self.fetch_url
            params = {
                'db': 'pubmed',
                'id': ','.join(id_batch)
            }

            # Add API key if available
            if self.api_key:
                params['api_key'] = self.api_key

            xml = ""
            max_retries = 3
            retry_delay = 1

            for attempt in range(max_retries):
                try:
                    response = requests.get(url, params=params, headers=headers, timeout=30)
                    response.raise_for_status()
                    xml = response.text
                    break
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        # Rate limited - wait longer and retry
                        wait_time = retry_delay * (2 ** attempt)
                        logger.warning(f"Rate limited by NCBI, waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        if attempt == max_retries - 1:
                            logger.error(f"Rate limit exceeded after {max_retries} retries for batch {low}-{high}")
                            raise
                    else:
                        raise
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Fetch failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        logger.error(f"Error fetching articles batch {low}-{high}: {e}", exc_info=True)
                        raise

            if not xml:
                low += batch_size
                high += batch_size
                continue

            root = ET.fromstring(xml)

            for article_node in root.findall(".//PubmedArticle"):
                articles.append(PubMedArticle.from_xml(ET.tostring(article_node)))

            low += batch_size
            high += batch_size

            # Rate limiting delay between batches
            if low < len(ids):
                time.sleep(REQUEST_DELAY)

        return articles

    def get_pmc_full_text(self, pmc_id: str) -> Optional[str]:
        """
        Fetch full text from PubMed Central for an article with a PMC ID.

        Args:
            pmc_id: The PMC ID (e.g., "PMC1234567" or just "1234567")

        Returns:
            The full text of the article as plain text, or None if not available.
        """
        # Normalize PMC ID
        if pmc_id.upper().startswith('PMC'):
            pmc_id = pmc_id[3:]

        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            'db': 'pmc',
            'id': pmc_id,
            'rettype': 'xml'
        }

        if self.api_key:
            params['api_key'] = self.api_key

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            xml_content = response.text

            # Parse the XML to extract text content
            root = ET.fromstring(xml_content)

            # Extract all text from body sections
            text_parts = []

            # Get the article title
            title = root.find('.//article-title')
            if title is not None:
                text_parts.append(f"# {''.join(title.itertext())}\n")

            # Get abstract
            abstract = root.find('.//abstract')
            if abstract is not None:
                text_parts.append("## Abstract\n")
                for p in abstract.findall('.//p'):
                    text_parts.append(''.join(p.itertext()) + "\n")

            # Get body sections
            body = root.find('.//body')
            if body is not None:
                for sec in body.findall('.//sec'):
                    # Get section title
                    sec_title = sec.find('./title')
                    if sec_title is not None:
                        text_parts.append(f"\n## {''.join(sec_title.itertext())}\n")

                    # Get paragraphs in section
                    for p in sec.findall('./p'):
                        text_parts.append(''.join(p.itertext()) + "\n")

            if text_parts:
                return '\n'.join(text_parts)
            else:
                logger.warning(f"No text content found in PMC article {pmc_id}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching PMC article {pmc_id}: {e}")
            return None
        except ET.ParseError as e:
            logger.error(f"Error parsing PMC XML for {pmc_id}: {e}")
            return None


def get_pmc_full_text(pmc_id: str) -> Optional[str]:
    """
    Module-level function to fetch full text from PubMed Central.

    Args:
        pmc_id: The PMC ID (e.g., "PMC1234567" or just "1234567")

    Returns:
        The full text of the article, or None if not available.
    """
    service = PubMedService()
    return service.get_pmc_full_text(pmc_id)


# Keep the old function for backward compatibility but have it call the new one
def search_articles_by_date_range(filter_term: str, start_date: str, end_date: str, date_type: str = "publication", sort_by: str = "relevance") -> tuple[List['CanonicalResearchArticle'], Dict[str, Any]]:
    """
    DEPRECATED: Use search_articles() instead.

    This function is kept for backward compatibility and now returns (articles, metadata) tuple.
    """
    # Just call the new unified search function
    articles, metadata = search_articles(
        query=filter_term,
        max_results=_get_pubmed_max_results(),
        offset=0,
        sort_by=sort_by,
        start_date=start_date,
        end_date=end_date,
        date_type=date_type
    )
    return articles, metadata


def fetch_articles_by_ids(pubmed_ids: List[str]) -> List[PubMedArticle]:
    """
    Fetch PubMed articles by their PMID.

    Args:
        pubmed_ids: List of PubMed IDs to fetch

    Returns:
        List of PubMedArticle objects
    """
    service = PubMedService()
    return service._get_articles_from_ids(pubmed_ids)


def search_pubmed_count(search_term: str) -> int:
    """
    Get the count of results for a PubMed search without fetching articles.

    Args:
        search_term: PubMed search query

    Returns:
        Number of results found
    """
    service = PubMedService()
    _, count = service._get_article_ids(search_term, max_results=1)  # Only get count, not actual results
    return count
