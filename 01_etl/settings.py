import os

from pydantic import BaseModel


class Settings(BaseModel):
    """Настройки"""

    chunk_size: int = int(os.environ.get('CHUNK_SIZE', 1000))
    etl_state_storage: str = os.environ.get('ETL_STATE_STORAGE', 'etl_state.json')
    etl_state_key: str = os.environ.get('ETL_STATE_KEY', 'updated_at')
    es_url: str = os.environ.get('ES_MOVIES_URL', 'http://movies-elasticsearch:9200')

    DSL = {
            'dbname': os.environ.get('DB_NAME'),
            'user': os.environ.get('DB_USER'),
            'password': os.environ.get('DB_PASSWORD'),
            'host': os.environ.get('DB_HOST', 'movies-postgresql'),
            'port': os.environ.get('DB_PORT', 5432),
        }