import asyncio
from parsers import *

arxiv_urls = [
    'https://arxiv.org/abs/2601.00417',
    'https://arxiv.org/abs/2601.02780',
    'https://arxiv.org/abs/2601.08584',
    'https://arxiv.org/abs/2601.21204',
    'https://arxiv.org/abs/2602.00462',
    'https://arxiv.org/abs/2602.04705',
    'https://arxiv.org/abs/2602.08071',
    'https://arxiv.org/abs/2602.10604',
    'https://arxiv.org/abs/2602.13367',
    'https://arxiv.org/abs/2602.15029',
    'https://arxiv.org/abs/2602.15763',
    'https://arxiv.org/abs/2603.05498',
    'https://arxiv.org/abs/2603.11510',
    'https://arxiv.org/abs/2603.15031',
    'https://arxiv.org/abs/2603.15569',
    'https://arxiv.org/abs/2604.14191',
    'https://arxiv.org/abs/2604.12374',
    'https://arxiv.org/abs/2605.05365',
    'https://arxiv.org/abs/2605.18855',
    'https://arxiv.org/abs/2605.22791',
    'https://arxiv.org/abs/2605.26494'
]
bbclub_search = 'программирование'

async def main():
    await ArxivParser(arxiv_urls).launch()
    await BiblioclubParser(bbclub_search).launch()

asyncio.run(main())