from os.path import dirname, abspath
from json import load
from sqlalchemy import create_engine, BigInteger, String, Text
from sqlalchemy.engine import URL
from pgvector.sqlalchemy import Vector
from cleaner import *
from vectorizer import *
from time import perf_counter

st = perf_counter()
print("Запуск")

try:
    with open(f'{dirname(abspath(__file__))}/config.json', 'r', encoding='utf-8') as f:
        config = load(f)
except Exception as e:
    raise Exception(f"Ошибка чтения config.json: {e}")

try:
    cleaner = DataCleaner()
    print("Клинер инициализирован")
    vectorizer = DataVectorizer()
    print("Векторизатор инициализирован")
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
    print("База данных подключена")
except Exception as e:
    raise Exception(f"Ошибка подключения к базе данных: {e}")

# Подготовка данных
try:
    print("Очистка...")
    df = cleaner.get_df(config['DATA_DIR_PATH'])
    df = cleaner.get_basic_clean(df)
    cleaner.clean_arxiv_artifacts(df)
    cleaner.clean_biblioclub_artifacts(df)
    df = cleaner.get_cleaned_duplicates(df)
    print("Очищено")
except Exception as e:
    raise Exception(f"Ошибка при очистке: {e}")

try:
    print("Векторизация...")
    df_chunks = cleaner.get_cleaned_chunks(df, vectorizer.get_splitter())
    df_embedded = vectorizer.get_embeddings(df_chunks)
    df_embedded['embedding'] = df_embedded['embedding'].apply(lambda v: str(v))
    print("Векторизовано")
except Exception as e:
    raise Exception(f"Ошибка при создании эмбеддингов: {e}")

# Импорт в базу данных
dtype_mapping = {
    'document_id': BigInteger(),
    'content': Text(),
    'category': String(50),
    'embedding': Vector(1024) # тестируется
}

try:
    print("Импорт ...")
    df_chunks.to_sql(
        name=config['DB_TABLE'],
        con=engine,
        if_exists='append',
        index=False,
        dtype=dtype_mapping
    )
    print("Импорт завершён")
except Exception as e:
    raise Exception(f"Ошибка при пополнении базы данных: {e}")

en = perf_counter()
print(f"Готово, {en - st} сек")