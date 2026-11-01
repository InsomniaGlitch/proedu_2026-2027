from langchain_text_splitters import RecursiveCharacterTextSplitter as RCTP
from sentence_transformers import SentenceTransformer
import pandas as pd

class DataVectorizer:
    "Embeddings maker based on BAAI/bge-m3"
    def __init__(self):
        self.splitter = RCTP(chunk_size=1000, chunk_overlap=150)

    def get_splitter(self) -> RCTP:
        "Returns splitter of the DataVectorizer"
        return self.splitter

    @staticmethod
    def get_embeddings(df_chunks: pd.DataFrame) -> None:
        "Returns embedded DataFrame to a DataFrame"
        model = SentenceTransformer('BAAI/bge-m3')
        vectors = model.encode(df_chunks['content'].to_list(), show_progress_bar=True)
        df_chunks['embedding'] = list(vectors)
        df_chunks = df_chunks.drop_duplicates(subset=['embedding'])
        return df_chunks