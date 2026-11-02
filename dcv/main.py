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
print("Запуск", flush=True)

try:
    with open(f'{dirname(abspath(__file__))}/config.json', 'r', encoding='utf-8') as f:
        config = load(f)
except Exception as e:
    raise Exception(f"Ошибка чтения config.json: {e}")

try:
    cleaner = DataCleaner()
    print("Клинер инициализирован", flush=True)
    vectorizer = DataVectorizer()
    print("Векторизатор инициализирован", flush=True)
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
    print("Подключено к базе данных", flush=True)
except Exception as e:
    raise Exception(f"Ошибка при подключении к базе данных: {e}")

try:
    print("Очистка...", flush=True)
    df = cleaner.get_df(config['DATA_DIR_PATH'])
    df = cleaner.get_basic_clean(df)
    df = cleaner.get_cleaned_arxiv_artifacts(df)
    df = cleaner.get_cleaned_biblioclub_artifacts(df)
    df = cleaner.get_basic_clean(df)
    df = cleaner.get_cleaned_duplicates(df)
    print("Очищено", flush=True)
except Exception as e:
    raise Exception(f"Ошибка при очистке данных: {e}")

try:
    print("Заполнение таблицы документов...", flush=True)
    df['text'].to_sql(
        name=config['DOC_TABLE'],
        con=engine,
        if_exists='append',
        index=False,
        dtype={'text': Text()}
    )
    print("Готово", flush=True)
except Exception as e:
    raise Exception(f"Ошибка при импорте документов: {e}")

df = df.rename(columns={'file_name': 'document_id'})
df['document_id'] = arange(1, len(df['document_id']) + 1)

try:
    print("Векторизация...", flush=True)
    df_chunks = cleaner.get_cleaned_chunks(df, vectorizer.get_splitter())
    df_embedded = vectorizer.get_embeddings(df_chunks)
    df_embedded['embedding'] = df_embedded['embedding'].apply(lambda v: str(v))
    print("Векторизировано", flush=True)
except Exception as e:
    raise Exception(f"Ошибка при векторизации: {e}")

dtype_mapping = {
    'document_id': BigInteger(),
    'content': Text(),
    'category': String(50),
    'embedding': Vector(1024)
}

try:
    print("Заполнение таблицы эмбеддингов...", flush=True)
    df_chunks.to_sql(
        name=config['VEC_TABLE'],
        con=engine,
        if_exists='append',
        index=False,
        dtype=dtype_mapping,
        chunksize=512
    )
    print("Готово", flush=True)
except Exception as e:
    raise Exception(f"Ошибка при заполнении таблицы эмбеддингов: {e}")

en = perf_counter()
print(f"Завершено, {en - st} с")