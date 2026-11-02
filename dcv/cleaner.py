import pandas as pd
from glob import glob
from os import PathLike
from langchain_text_splitters import RecursiveCharacterTextSplitter as RCTP

class DataCleaner:
    "Basic data cleaner for text"
    def __init__(self):
        pass

    @staticmethod
    def get_df(data_absolute_path: PathLike) -> pd.DataFrame:
        "Returns DataFrame populated with data from the specified directory"
        file_paths = glob('*.txt', root_dir=data_absolute_path)
        
        data = []
        for path in file_paths:
            with open(f'{data_absolute_path}\\{path}', 'r', encoding='utf-8') as f:
                data.append({'file_name': path, 'text': f.read()})
    
        return pd.DataFrame(data)

    @staticmethod
    def get_basic_clean(df: pd.DataFrame) -> pd.DataFrame:
        "Returns DataFrame cleaned of typos and bad imports"
        df['text'] = df['text'].str.lower()
        df['text'] = df['text'].str.strip()
        df['text'] = df['text'].str.replace('\n', ' ')
        df['text'] = df['text'].str.replace(r'\s+', ' ', regex=True)
        df = df[df['text'].str.strip() != '']
        df = df[df['text'].str.len() > 10]
        return df

    @staticmethod
    def get_cleaned_arxiv_artifacts(df: pd.DataFrame) -> pd.DataFrame:
        "Returns DataFrame cleaned of arXiv artifacts"
        mask = df['file_name'].str.contains('arxiv', na=False)
        if not mask.any():
            return df
        
        def trim_text(row):
            text_lower = row['text'].lower()

            start = text_lower.find('abstract')
            start = start if start != -1 else 0

            end = text_lower.rfind('experimental support, please view the build logs for errors')
            end = end if end != -1 else 0

            return row['text'][start:end]

        df.loc[mask, 'category'] = 'llm' # example
        df.loc[mask, 'text'] = df.loc[mask].apply(trim_text, axis=1)
        df.loc[mask, 'text'] = df.loc[mask, 'text'].str.replace('abstract download pdf contents reading mode colour theme', '')
        return df

    @staticmethod
    def get_cleaned_biblioclub_artifacts(df: pd.DataFrame) -> pd.DataFrame:
        "Returns DataFrame cleaned of BiblioClub artifacts"

        # Source - https://stackoverflow.com/a/1884277
        # Posted by Todd Gamblin, modified by community. See post 'Timeline' for change history
        # Retrieved 2026-11-01, License - CC BY-SA 4.0
        def find_nth(haystack: str, needle: str, n: int) -> int:
            start = haystack.find(needle)
            while start >= 0 and n > 1:
                start = haystack.find(needle, start+len(needle))
                n -= 1
            return start

        mask = df['file_name'].str.contains('biblioclub', na=False)
        if not mask.any():
            return df

        def process_row(row):
            row_str = row['text']
            artifact_idx = find_nth(row_str, ' ', 6)

            if artifact_idx == -1:
                return row_str

            artifact = row_str[:artifact_idx]
            return row_str.replace(artifact, '')

        df.loc[mask, 'text'] = df.loc[mask].apply(process_row, axis=1)
        df.loc[mask, 'category'] = 'programming' # example
        return df

    @staticmethod
    def get_cleaned_duplicates(df: pd.DataFrame) -> pd.DataFrame:
        "Returns DataFrame cleaned of duplicates"
        df = df.drop_duplicates(subset=['text'], keep='first')
        return df

    @staticmethod
    def get_cleaned_chunks(df: pd.DataFrame, splitter: RCTP) -> pd.DataFrame:
        "Returns DataFrame with content converted into cleaned chunks"
        df['chunks'] = df['text'].apply(lambda text: splitter.split_text(text))
        df_chunks = df.explode('chunks').reset_index(drop=True)
        df_chunks = df_chunks.rename(columns={'chunks': 'content'})
        df_chunks['chunks_clean'] = df_chunks['content'].str.strip().str.replace(r'\s+', ' ', regex=True)
        df_chunks = df_chunks.drop_duplicates(subset=['chunks_clean'], keep='first')
        df_chunks = df_chunks.drop(columns=['chunks_clean', 'text'])
        return df_chunks.dropna(subset=['content'])