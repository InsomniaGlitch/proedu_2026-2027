from sqlalchemy import create_engine, text, Engine, MetaData
from sqlalchemy.engine import URL
from io import BytesIO
import pandas as pd

def setup_engine(dbms: str, 
                 driver: str, 
                 db_login: str, 
                 db_password: str, 
                 db_host: str, 
                 db_port: int, 
                 db_name: str) -> Engine:
    "Validates database attributes and returns engine."
    if any(not db_char for db_char in (dbms, driver, db_login, db_password, db_port, db_name)):
        raise ValueError("Database attributes must not be empty.")

    supported = ['postgresql', 'mysql']
    management_system = dbms.strip().lower()
    for i in range(len(supported)):
        if management_system in supported[i]:
            management_system = supported[i]
            break
    else:
        raise TypeError(f"{dbms} is unsupported.")

    driv = driver.strip().lower()
    host = db_host.strip().lower()
    if not host:
        host = 'localhost'
    name = db_name.strip()

    db_url = URL.create(
        drivername=f"{management_system}+{driv}",
        username=db_login,
        password=db_password,
        host=host,
        port=db_port,
        database=name
    )

    try:
        engine = create_engine(db_url)
    except Exception as e:
        raise Exception(f"Engine setup failed: {e}")
    
    return engine

def inspect_database(engine: Engine) -> dict[str, dict[str, list[dict[str, str | bool]] | list[str]]]:
    "Inspects engine metadata and returns database structure as dictionary"
    metadata = MetaData()
    try:
        metadata.reflect(bind=engine)
    except Exception as e:
        raise Exception(f"Failed on metadata reflection: {e}")

    db_structure = {}

    for table, table_obj in metadata.tables.items():
        db_structure[table] = {
            "columns": [],
            "primary_keys": [key.name for key in table_obj.primary_key.columns],
            "foreign_keys": []
        }

        for column in table_obj.columns:
            db_structure[table]["columns"].append({
                "name": column.name,
                "type": str(column.type),
                "nullable": column.nullable
            })

        for fk in table_obj.foreign_keys:
            db_structure[table]["foreign_keys"].append({
                "constrained_column": fk.parent.name,
                "referred_table": fk.column.table.name,
                "referred_column": fk.column.name
            })

    return db_structure

def list_head(engine: Engine, db_stucture: dict, table: str, limit: int = 3) -> list[list]:
    "Returns first rows as list"
    if not isinstance(limit, int) or not (1 <= limit <= 5):
        raise ValueError(f"limit must be an int in range(1, 5), not {limit}")
    if table not in db_stucture:
        raise ValueError(f"There is no table with name {table}")
    
    try: 
        with engine.connect() as connection:
            q = f"SELECT * FROM {table} LIMIT 5"
            query = text(q)
            result = connection.execute(query)

        result_list = [
            [db_stucture[table]['columns'][i]['name'] for i in range(len(db_stucture[table]['columns']))]
        ]
        for row in result:
            result_list.append(row)
    except Exception as e:
        raise Exception(f"{q} query failure: {e}")
    
    return result_list

def insert_csv(csv_bytes: bytes, delimiter: str, table: str, engine: Engine) -> None:
    "Decodes file bytes and inserts them into connected database"
    df = pd.read_csv(BytesIO(csv_bytes), sep=delimiter, encoding='utf-8')
    try:
        df.to_sql(table, con=engine, if_exists='append', index=False, chunksize=500)
    except Exception as e:
        raise Exception(f"Import failed: {e}")