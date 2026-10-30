import asyncio
from os.path import dirname, abspath
from random import randint
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

curdir = dirname(abspath(__file__))

class ArxivParser:
    def __init__(self, search, page = 1):
        self.search = f'https://arxiv.org/search/cs?query={search}&searchtype=all&abstracts=hide&order=-announced_date_first&start={(page - 1) * 50}'
    
    async def launch(self):
        async with Stealth().use_async(async_playwright()) as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            await page.goto(self.search)
            links_locator = page.locator('#main-container .content ol li p a')
            await links_locator.first.wait_for(state='attached')
            book_links = await links_locator.all()
            
            urls = []
            for el in book_links:
                href = await el.get_attribute('href')
                if href:
                    urls.append(href)
            
            tasks = [self._scrape_page(context, url) for url in urls[:1]]
            results = await asyncio.gather(*tasks)

            c = 0
            for res in results:
                with open(f"{curdir}/parsed_data/arxiv_document_{c}.txt", 'x', encoding='utf-8') as f:
                    f.write(res)
                c += 1

            await browser.close()

    @staticmethod
    async def _scrape_page(context, url):
        page = await context.new_page()
        await page.goto(url, wait_until='domcontentloaded')
        await page.wait_for_timeout(randint(900, 1100))
        await page.get_by_text('HTML (experimental)').last.click()
        text = await page.locator('body').inner_text()
        await page.close()
        return text

class BiblioclubParser:
    def __init__(self, search_input):
        self.full_search = f'https://biblioclub.ru/index.php?page=search&search_input={search_input}'
        self._auth = False

    async def save_auth(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(self.full_search)
            await page.wait_for_timeout(30 * 1000)
            await context.storage_state(path=f'{curdir}/auth_state.json')
            await browser.close()

    async def launch(self):
        if not self._auth:
            await self.save_auth()
            self._auth = True
        
        async with Stealth().use_async(async_playwright()) as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(storage_state=f'{curdir}/auth_state.json')
            page = await context.new_page()

            await page.goto(self.full_search)
            
            links_locator = page.locator('.book-item-area .book-item-area .book-item .book-info .block_header a')
            await links_locator.first.wait_for(state='attached')
            book_links = await links_locator.all()
            
            urls = []
            for el in book_links:
                href = await el.get_attribute('href')
                if href:
                    urls.append(f'https://biblioclub.ru/{href}')
            
            tasks = [self._scrape_page(context, url) for url in urls]
            results = await asyncio.gather(*tasks)
            
            c = 0
            for res in results:
                with open(
                    f"{curdir}/parsed_data/biblioclub_document_{c}.txt", 'x', encoding='utf-8'
                ) as f:
                    f.write(res)
                c += 1

            await browser.close()

    @staticmethod
    async def _scrape_page(context, url):
        page = await context.new_page()
        await page.goto(url, wait_until='domcontentloaded')
        await page.get_by_text('Читать (v3)').click()
        
        try:
            await page.get_by_text('Читать', ).click()
        except:
            pass

        div_el = page.locator('input.pg_input').locator('xpath=..')
        div_text = await div_el.inner_text()
        total_pages = int(div_text.split('/')[-1].strip())
        
        texts = []
        page_number = 1
        while page_number != total_pages: # despite that condition, clicks != total_pages(
            texts.append(await page.locator('body').inner_text())
            await page.locator('.ud_but').last.click()
            await page.wait_for_timeout(randint(80, 100))
            page_number += 1
        
        await page.close()
        return "".join(texts)