"""
YepSearch Search Provider

Web search provider using YepSearch (webscout) search engine.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from super_rag.schema.view_models import WebSearchResultItem
from super_rag.websearch.search.base_search import BaseSearchProvider
from super_rag.websearch.utils.url_validator import URLValidator

logger = logging.getLogger(__name__)

try:
    from webscout import YepSearch
except ImportError:
    logger.error("webscout package is required. Install with: pip install webscout")
    raise


class YepSearchProvider(BaseSearchProvider):
    """
    YepSearch search provider implementation.

    Uses the webscout library's YepSearch to perform web searches.
    """

    def __init__(self, config: dict = None):
        """
        Initialize YepSearch provider.

        Args:
            config: Provider configuration
        """
        super().__init__(config)
        self.supported_engines = ["yep", "yepsearch"]
        
        # Get browser config from config, with defaults
        self.browser_config = config.get("browser_config", {}) if config else {}
        self.timeout = self.browser_config.get("timeout", 15)
        self.proxies = self.browser_config.get("proxies", None)
        self.verify = self.browser_config.get("verify", False)
        self.region = self.browser_config.get("region", "all")
        self.safesearch = self.browser_config.get("safesearch", "moderate")

    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: int = 30,
        locale: str = "zh-CN",
        source: Optional[str] = None,
    ) -> List[WebSearchResultItem]:
        """
        Perform web search using YepSearch.

        Args:
            query: Search query (can be empty for site-specific browsing)
            max_results: Maximum number of results to return
            timeout: Request timeout in seconds
            locale: Browser locale
            source: Domain or URL for site-specific search. When provided, search will be limited to this domain.

        Returns:
            List of search result items
        """
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

        # Use the configured timeout or the method parameter timeout, whichever is smaller
        search_timeout = min(self.timeout, timeout)

        # Perform search
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, 
            self._search_sync, 
            final_query, 
            max_results, 
            search_timeout
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

    def _search_sync(self, query: str, max_results: int, timeout: int) -> List[WebSearchResultItem]:
        """
        Synchronous search implementation.

        Args:
            query: Search query
            max_results: Maximum number of results
            timeout: Request timeout

        Returns:
            List of search result items
        """
        # Create YepSearch instance with configuration
        yep = YepSearch()

        # Perform search
        try:
            search_results = list(
                yep.text(
                    query,
                    region=self.region,
                    safesearch=self.safesearch,
                    max_results=max_results
                )
            )
        except Exception as e:
            error_msg = str(e)
            # Handle UTF-8 encoding errors from orjson
            if "not valid UTF-8" in error_msg or "surrogates not allowed" in error_msg:
                logger.warning(f"YepSearch failed due to UTF-8 encoding issue: {error_msg}")
                # Return empty results instead of raising
                return []
            # Handle SSL/TLS errors
            if "TLS connect error" in error_msg or "SSL" in error_msg:
                logger.warning(f"YepSearch failed due to SSL/TLS error: {error_msg}")
                return []
            # For other errors, log and re-raise
            logger.error(f"YepSearch failed: {error_msg}")
            raise

        # Convert results to our format
        results = []
        for i, result in enumerate(search_results):
            # Validate URL
            url = result.get("href", "")
            if not URLValidator.is_valid_url(url):
                continue

            # Get snippet from body field
            snippet = result.get("body", "")
            title = result.get("title", "")

            results.append(
                WebSearchResultItem(
                    rank=i + 1,
                    title=title,
                    url=url,
                    snippet=snippet,
                    domain=URLValidator.extract_domain(url),
                    timestamp=datetime.now(),
                )
            )

        return results

    def get_supported_engines(self) -> List[str]:
        """
        Get list of supported search engines.

        Returns:
            List of supported search engine names
        """
        return self.supported_engines.copy()


import asyncio

if __name__ == "__main__":
    provider = YepSearchProvider()
    async def main():
        results = await provider.search("python")
        print(results)
    asyncio.run(main())