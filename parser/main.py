import asyncio
from parsers import *

arxiv_search = 'llm'
bbclub_search = 'программирование'

async def main():
    await ArxivParser(arxiv_search).launch()
    await BiblioclubParser(bbclub_search).launch()

asyncio.run(main())