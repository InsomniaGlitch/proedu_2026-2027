import gc
import torch
from os.path import dirname, abspath
from json import load
from sqlalchemy import create_engine, BigInteger, String, Text
from sqlalchemy.engine import URL
from pgvector.sqlalchemy import Vector
from numpy import arange
from time import perf_counter
from cleaner import *
from vectorizer import *

st = perf_counter()
print("DCV запущен", flush=True)

try:
    with open(f'{dirname(abspath(__file__))}/config.json', 'r', encoding='utf-8') as f:
        config = load(f)
except Exception as e:
    raise Exception(f"Ошибка при чтении config.json: {e}")

try:
    cleaner = DataCleaner()
    print("Клинер инициализирован", flush=True)
    vectorizer = DataVectorizer()
    print("Векторайзер инициализирован", flush=True)
except Exception as e:
    raise Exception(f"Ошибка инициализации модуля: {e}")

try:
    engine = create_engine(URL.create(
        drivername=f"{config['DBMS'].lower()}+{config['DRIVER']}",
        username=config['DB_LOGIN'],
        password=config['DB_PASSWORD'],
        host=config['DATABASE_HOST'],
        port=config['DATABASE_PORT'],
        database=config['DB_NAME']
    ))
    print("База данных подключена", flush=True)
except Exception as e:
    raise Exception(f"Ошибка при подключении к базе данных: {e}")

print("Очистка...", flush=True)
try:
    df = cleaner.get_df(config['DATA_DIR_PATH'])
    df = cleaner.get_basic_clean(df)
    df = cleaner.get_cleaned_arxiv_artifacts(df)
    df = cleaner.get_cleaned_biblioclub_artifacts(df)
    df = cleaner.get_basic_clean(df)
    df = cleaner.get_cleaned_duplicates(df)
    print("Очищеноиии", flush=True)
except Exception as e:
    raise Exception(f"Ошибка при очистке: {e}")

print("Заполнение таблицы документов...", flush=True)
try:
    df[['filename', 'text']].to_sql(
        name=config['DOC_TABLE'],
        con=engine,
        if_exists='append',
        index=False,
        dtype={
            'filename': String(260),
            'text': Text()
        }
    )
    print("Готово", flush=True)
except Exception as e:
    raise Exception(f"Ошибка при импорте документов: {e}")

df = df.rename(columns={'filename': 'document_id'})
df['document_id'] = arange(1, len(df['document_id']) + 1)

batch_rows = 10
total_rows = len(df)
cuda_available = torch.cuda.is_available()

print("Векторизация и заполнение базы данных чанками...", flush=True)
try:
    for i in range(0, total_rows, batch_rows):
        print(f'{i / total_rows * 100:.1f}%', flush=True)
        df_mini = df.iloc[i : i + batch_rows].copy()
        df_chunks = cleaner.get_cleaned_chunks(df_mini, vectorizer.get_splitter())
        df_embedded = vectorizer.get_embeddings(df_chunks, use_gpu=cuda_available)
        
        df_embedded.to_sql(
            name=config['VEC_TABLE'],
            con=engine,
            if_exists='append',
            index=False,
            dtype={
                'document_id': BigInteger(),
                'content': Text(),
                'category': String(50),
                'embedding': Vector(1024)
            }
        )

        del df_mini, df_chunks, df_embedded
        gc.collect()
        if cuda_available:
            torch.cuda.empty_cache()
        
    print("Готово", flush=True)
except Exception as e:
    raise Exception(f"Ошибка при векторизации или заполнении: {e}")

en = perf_counter()
print(f"Завершено, {en - st} сек")