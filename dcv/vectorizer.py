import gc
import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter as RCTP
from sentence_transformers import SentenceTransformer

class DataVectorizer:
    "Embeddings maker based on BAAI/bge-m3"
    def __init__(self):
        self.splitter = RCTP(chunk_size=1000, chunk_overlap=150)

    def get_splitter(self) -> RCTP:
        "Returns splitter of the DataVectorizer"
        return self.splitter

    @staticmethod
    def get_embeddings(df_chunks: pd.DataFrame, use_gpu: bool = False) -> pd.DataFrame:
        "Returns embedded DataFrame"
        if df_chunks.empty:
            return df_chunks
        texts = df_chunks['content'].fillna('').astype(str).to_list()

        if use_gpu:
            model = SentenceTransformer('BAAI/bge-m3', device='cuda')
            # model.half()

            vectors = model.encode(
                texts,
                batch_size=128,
                show_progress_bar=True,
                convert_to_numpy=True
            )
        else:
            model = SentenceTransformer('BAAI/bge-m3')
            vectors = model.encode(
                texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True
            )
        
        df_chunks['embedding'] = list(vectors)
        df_chunks = df_chunks[~df_chunks['embedding'].map(tuple).duplicated(keep='first')]

        del vectors, texts
        gc.collect()

        return df_chunks