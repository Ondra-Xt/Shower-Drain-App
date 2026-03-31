class GenericScraper:
    """Base class for all scrapers."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        
    def scrape(self, search_term: str):
        """Scrapes the website for the given search term.
        
        Args:
            search_term: The term to search for (e.g., 'Duschrinne').
            
        Returns:
            A list of Offer objects.
        """
        raise NotImplementedError("Subclasses must implement scrape method")
