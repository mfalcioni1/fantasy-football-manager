import os
import asyncio
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright

class WebScraper:
    def __init__(self, download_dir='data', headless=True):
        self.download_dir = download_dir
        self.scraped_data = []
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
        self.playwright = sync_playwright().start()  # Start Playwright here
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context(accept_downloads=True)
        self.page = self.context.new_page()

    def navigate_to_page(self, url):
        self.page.goto(url)
        self.page.wait_for_load_state('networkidle')

    def select_dropdown(self, selector, value):
        self.page.select_option(selector, value)

    def click_button(self, selector):
        self.page.click(selector)

    def download_file(self, download_button_selector, new_file_name, timeout=20):
        with self.page.expect_download() as download_info:
            self.page.click(download_button_selector)
        download = download_info.value
        download_path = download.path()
        new_file_path = os.path.join(self.download_dir, new_file_name)
        download.save_as(new_file_path)  # Use save_as for specifying the path directly
        return new_file_path
    
    def reset_scraped_data(self):
        """
        Clears the scraped data, preparing for a new scraping task.
        """
        self.scraped_data = []

    def create_scrape_function(self, function_name, *args, **kwargs):
        """
        Factory function to create and return a scraping function with predefined parameters.

        :param function_name: The name of the scraping function defined in this class.
        :param args: Positional arguments to pass to the scraping function.
        :param kwargs: Keyword arguments to pass to the scraping function.
        :return: A function that when called, executes the specified scraping function with the provided arguments.
        """
        method = getattr(self, function_name, None)
        if not method:
            raise AttributeError(f"Method {function_name} not found in WebScraper")

        def scrape_function():
            # Make 'page' available for the method call
            return method(*args, **kwargs)

        return scrape_function

    def scrape_table_data(self, selector):
        """
        Scrapes data from a table by extracting text from each table cell (td).
        """
        # Find all table cell elements by XPath
        cells = self.page.query_selector_all(f'xpath={selector}')

        # Extract and return the text content from each cell
        page_data = [cell.inner_text() for cell in cells]

        # Append the data to the list of scraped data
        self.scraped_data.append(page_data)

    def scrape_other_data(self, selector):
        pass

    def paginate_scrape_selector(self, next_page_selector, scrape_function, wait_selector=None):
        """
        Navigates through pages using a 'next page' button or link and applies a given function on each page.

        :param next_page_selector: CSS selector for the 'next page' link or button.
        :param scrape_function: Function to call for scraping/interacting with the page.
                                It must accept a single argument, the page object.
        :param wait_selector: Optional. CSS selector to wait for after navigating to a new page, indicating the page has loaded.
        """
        while True:
            # Apply the scrape function on the current page
            scrape_function()

            # Try to find the 'next page' link or button
            next_page_link = self.page.query_selector(next_page_selector)
            if next_page_link and next_page_link.is_visible():
                # Click the 'next page' link/button and wait for navigation
                with self.page.expect_navigation():
                    next_page_link.click()

                # Wait for the next page to reach a certain load state, e.g., 'networkidle'
                self.page.wait_for_load_state('networkidle')

                # Optionally, wait for a specific selector to appear on the new page
                if wait_selector:
                    self.page.wait_for_selector(wait_selector, state="visible")
            else:
                # Exit if no 'next page' link/button is found or it's not visible
                break

    def paginate_scrape_url(self, base_url, scrape_function, content_check, start_page=1, page_param='page'):
        """
        Paginates through pages by modifying the URL directly and applies a given function on each page.

        :param base_url: The base URL without the page number.
        :param scrape_function: Function to call for scraping/interacting with the page.
                                It must accept a single argument, the page object.
        :param start_page: The starting page number.
        :param page_param: The query parameter used for the page number in the URL.
        """
        current_page = start_page
        while True:
            # Construct the URL for the current page
            page_url = f"{base_url}&{page_param}={current_page}"
            self.navigate_to_page(page_url)

            # Apply the scrape function on the current page
            scrape_function()

            # Check for a condition to determine if there are more pages. This could be
            # the presence of specific content that indicates a non-empty page.
            # For example, you might check if a certain CSS selector exists that would
            # not be present on an empty or final page. If such an element is not found,
            # assume this is the last page and break out of the loop.
            if not self.page.query_selector(content_check):
                break

            # Increment the page number for the next iteration
            current_page += 1

    def stop_browser(self):
        self.browser.close()
        self.playwright.stop()  # Properly stop Playwright

class AsyncWebScraper:
    def __init__(self, download_dir='data', headless=True):
        self.download_dir = download_dir
        self.scraped_data = []
        self.headless = headless
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    async def setup(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(accept_downloads=True)
        self.page = await self.context.new_page()

    async def navigate_to_page(self, url):
        await self.page.goto(url)
        await self.page.wait_for_load_state('networkidle')

    async def scrape_table_data(self, selector):
        cells = await self.page.query_selector_all(f'xpath={selector}')
        page_data = [await cell.inner_text() for cell in cells]
        self.scraped_data.append(page_data)

    async def close(self):
        await self.browser.close()
        await self.playwright.stop()

    @classmethod
    async def scrape_urls(cls, urls, selector, max_concurrent_tasks=5):
        async def scrape_url(url):
            scraper = cls()
            await scraper.setup()
            await scraper.navigate_to_page(url)
            await scraper.scrape_table_data(selector)
            data = scraper.scraped_data
            await scraper.close()
            return data

        async def run_scraping_tasks():
            tasks = []
            for url in urls:
                if len(tasks) >= max_concurrent_tasks:
                    # Wait for one task to finish before adding a new one
                    _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    tasks = [task for task in pending]
                task = asyncio.create_task(scrape_url(url))
                tasks.append(task)
            # Wait for all remaining tasks to complete
            if tasks:
                done, _ = await asyncio.wait(tasks)
            return [task.result() for task in done]

        return await run_scraping_tasks()