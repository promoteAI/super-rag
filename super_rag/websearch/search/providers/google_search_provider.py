"""
Google Search Provider

Web search provider using googlesearch-python library.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Optional

from super_rag.schema.view_models import WebSearchResultItem
from super_rag.websearch.search.base_search import BaseSearchProvider
from super_rag.websearch.utils.url_validator import URLValidator

logger = logging.getLogger(__name__)

try:
    from googlesearch import search
except ImportError:
    logger.warning("googlesearch-python package not found. Install with: pip install googlesearch-python")
    search = None


class GoogleSearchProvider(BaseSearchProvider):
    """
    Google search provider implementation.

    Uses the googlesearch-python library to perform web searches.
    """

    def __init__(self, config: dict = None):
        """
        Initialize Google search provider.

        Args:
            config: Provider configuration
        """
        super().__init__(config)
        self.supported_engines = ["google", "google_search"]
        
        if search is None:
            logger.warning("Google search provider initialized but googlesearch-python is not installed")

    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: int = 30,
        locale: str = "zh-CN",
        source: Optional[str] = None,
    ) -> List[WebSearchResultItem]:
        """
        Perform web search using Google.

        Args:
            query: Search query (can be empty for site-specific browsing)
            max_results: Maximum number of results to return
            timeout: Request timeout in seconds
            locale: Browser locale
            source: Domain or URL for site-specific search. When provided, search will be limited to this domain.

        Returns:
            List of search result items
        """
        if search is None:
            raise ImportError("googlesearch-python package is required. Install with: pip install googlesearch-python")

        # Validate parameters
        has_query = query and query.strip()
        has_source = source and source.strip()

        # Either query or source must be provided
        if not has_query and not has_source:
            raise ValueError("Either query or source must be provided")

        if max_results <= 0:
            raise ValueError("max_results must be positive")
        if max_results > 100:
            raise ValueError("max_results cannot exceed 100")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        # Construct query based on source restrictions
        final_query = query or ""
        target_domain = None

        if source:
            # Extract domain from source for site-specific search
            target_domain = URLValidator.extract_domain_from_source(source)

            if target_domain:
                if has_query:
                    # Query + site restriction
                    final_query = f"site:{target_domain} {query}"
                    logger.info(f"Using site-specific search with query for domain: {target_domain}")
                else:
                    # Site browsing without specific query
                    final_query = f"site:{target_domain}"
                    logger.info(f"Using site browsing for domain: {target_domain}")
            else:
                logger.warning(f"No valid domain found in source '{source}', using regular search")
                if not has_query:
                    raise ValueError("Invalid source domain and no query provided")

        # Perform search
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, 
            self._search_sync, 
            final_query, 
            max_results, 
            timeout, 
            locale
        )

        # Filter results to target domain when source is provided
        if target_domain:
            filtered_results = []
            for result in results:
                result_domain = URLValidator.extract_domain(result.url)
                if result_domain and result_domain.lower() == target_domain.lower():
                    filtered_results.append(result)

            # Re-rank filtered results
            for i, result in enumerate(filtered_results):
                result.rank = i + 1

            logger.info(f"Site-specific search completed: {len(filtered_results)} results from {target_domain}")
            return filtered_results

        return results

    def _search_sync(self, query: str, max_results: int, timeout: int, locale: str) -> List[WebSearchResultItem]:
        """
        Synchronous search implementation.

        Args:
            query: Search query
            max_results: Maximum number of results
            timeout: Request timeout
            locale: Browser locale

        Returns:
            List of search result items
        """
        results = []
        
        try:
            # Extract language code from locale (e.g., "zh-CN" -> "zh")
            lang = locale.split("-")[0] if "-" in locale else locale.split("_")[0] if "_" in locale else "en"
            
            # Perform search with error handling
            search_results = list(
                search(
                    query,
                    num_results=max_results,
                    lang=lang,
                    sleep_interval=1,  # Add delay to avoid blocking
                )
            )
            
            # Convert results to our format
            for i, url in enumerate(search_results):
                # Validate URL
                if not URLValidator.is_valid_url(url):
                    continue

                results.append(
                    WebSearchResultItem(
                        rank=i + 1,
                        title="",  # googlesearch-python doesn't provide titles
                        url=url,
                        snippet="",  # googlesearch-python doesn't provide snippets
                        domain=URLValidator.extract_domain(url),
                        timestamp=datetime.now(),
                    )
                )
                
                # Limit to max_results
                if len(results) >= max_results:
                    break
                    
        except Exception as e:
            logger.error(f"Google search error: {e}")
            # Return empty results instead of raising
            return []

        return results

    def get_supported_engines(self) -> List[str]:
        """
        Get list of supported search engines.

        Returns:
            List of supported search engine names
        """
        return self.supported_engines.copy()
