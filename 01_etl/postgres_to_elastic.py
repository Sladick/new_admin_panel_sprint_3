import logging
import os
from time import sleep
from typing import Any, Generator

import psycopg2
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers
from psycopg2.extras import DictCursor

import logger
from backoff import backoff
from validators import FilmworkPD
from state_store import JsonFileStorage, State
from settings import Settings

load_dotenv()
logging.basicConfig(**logger.settings)


class PostgresExtractor:
    """Забираем данные из таблиц film_work, genre, person"""

    def __init__(self) -> None:
        self.psql_dsn = {
            'dbname': os.environ.get('DB_NAME'),
            'user': os.environ.get('DB_USER'),
            'password': os.environ.get('DB_PASSWORD'),
            'host': os.environ.get('DB_HOST', 'movies-postgresql'),
            'port': os.environ.get('DB_PORT', 5432),
        }


    @backoff()
    def connect(self) -> bool:
        """создаём соединение"""
        try:
            conn = psycopg2.connect(**self.psql_dsn)
        except psycopg2.OperationalError:
            logging.error('Could not connect to postgresql.')
            return False
        else:
            logging.info('Connected to postgresql.')
            self.connection = conn
            self.cursor = conn.cursor(cursor_factory=DictCursor)
            return True

    def disconnect(self) -> None:
        """Закрывает соединение"""
        self.cursor.close()
        self.connection.close()

    def get_movies_data(self, updated_at: str) -> list[tuple[Any]]:
        """формируем запрос"""
        statement = """
        WITH base AS (
            SELECT
                id as filmwork_id,
                filmwork.modified as updated_at
            FROM content.film_work filmwork
            WHERE
                filmwork.modified > '{updated_at}'

            UNION

            SELECT
                filmwork.id as filmwork_id,
                genre.modified as updated_at
            FROM content.genre genre
                INNER JOIN content.genre_film_work genre_filmwork
                    ON genre.id = genre_filmwork.genre_id
                INNER JOIN content.film_work filmwork
                    ON genre_filmwork.film_work_id = filmwork.id
            WHERE
                genre.modified > '{updated_at}'

            UNION

            SELECT
                filmwork.id as filmwrok_id,
                person.modified as updated_at
            FROM content.person person
                INNER JOIN content.person_film_work person_filmwork
                    ON person.id = person_filmwork.person_id
                INNER JOIN content.film_work filmwork
                    ON person_filmwork.film_work_id = filmwork.id
            WHERE
                person.modified > '{updated_at}'

            ORDER BY
                updated_at
            LIMIT {chunk_size}
        )
        SELECT
            filmwork.id,
            filmwork.title,
            filmwork.description,
            filmwork.rating as imdb_rating,
            filmwork.type,
            filmwork.certificate,
            filmwork.created AS created_at,
            base.updated_at AS updated_at,
            COALESCE (
                json_agg(
                    DISTINCT jsonb_build_object(
                        'id', person.id,
                        'name', person.full_name
                    )
                ) FILTER (WHERE person.id is not null AND person_filmwork.role = 'actor'),
                '[]'
            ) as actors,
            COALESCE (
                json_agg(
                    DISTINCT jsonb_build_object(
                        'id', person.id,
                        'name', person.full_name
                    )
                ) FILTER (WHERE person.id is not null AND person_filmwork.role = 'writer'),
                '[]'
            ) as writers,
            COALESCE (
                ARRAY_AGG(DISTINCT person.full_name)
                    FILTER (WHERE person.id is not null AND person_filmwork.role = 'actor'),
                '{}'
            ) as actors_names,
            COALESCE (
                ARRAY_AGG(DISTINCT person.full_name)
                    FILTER (WHERE person.id is not null AND person_filmwork.role = 'writer'),
                '{}'
            ) as writers_names,
            COALESCE (
                ARRAY_AGG(DISTINCT person.full_name)
                    FILTER (WHERE person.id is not null AND person_filmwork.role = 'director'),
                '{}'
            ) as director,
            COALESCE (
                ARRAY_AGG (DISTINCT genre.name),
                '{}'
            ) as genre
        FROM base
            INNER JOIN content.film_work filmwork
                ON base.filmwork_id = filmwork.id
            LEFT JOIN content.person_film_work person_filmwork
                ON person_filmwork.film_work_id = filmwork.id
            LEFT JOIN content.person person
                ON person.id = person_filmwork.person_id
            LEFT JOIN content.genre_film_work genre_filmwork
                ON genre_filmwork.film_work_id = filmwork.id
            LEFT JOIN content.genre genre
                ON genre.id = genre_filmwork.genre_id
        GROUP BY
            filmwork.id,
            base.updated_at
        """.replace('{updated_at}', updated_at) \
                .replace('{chunk_size}', str(settings.chunk_size))

        curs = self.cursor

        curs.execute(statement)
        fetched_filmworks = curs.fetchall()

        return fetched_filmworks


class DataTransform:
    """Проверка и преобразование файлов для загрузки в Elastick"""

    def generate_docs(self, filmworks_raw: list) -> Generator:
        """Проверяем каждый полученный фильм"""
        keys = list(filmworks_raw[0].keys()) if filmworks_raw else []

        for filmwork_raw in filmworks_raw:
            filmwork_raw_dict = {key:filmwork_raw[key] for key in keys}
            filmwork_validated = FilmworkPD(**filmwork_raw_dict).dict()
            doc = {
                "_index": "movies",
                "_id": filmwork_validated['id'],
                "_source": filmwork_validated,
            }

            self.updated_at = filmwork_raw_dict['updated_at']

            yield doc


class ElasticSearchLoader:
    """Загружаем всё в Elastick"""

    def load_data(self, transformator: DataTransform, filmworks_raw) -> None:
        """Создаём документы в elasticsearch и возвращает последнее поле updated_at"""
        es = Elasticsearch(hosts=settings.es_url)
        try:
            helpers.bulk(es, transformator.generate_docs(filmworks_raw))
        except helpers.BulkIndexError as e:
            logging.error(e)


def data_transfer():
    while True:
        updated_at = State(state_storage).get_state(key=settings.etl_state_key)
        logging.info(f'state: {updated_at}')

        filmworks_raw = extractor.get_movies_data(updated_at)
        if not filmworks_raw:
            logging.info('records ended.')
            break

        loader.load_data(transformator, filmworks_raw)

        updated_at = transformator.updated_at
        state_storage.save_state({settings.etl_state_key: str(updated_at)})


if __name__ == '__main__':
    settings = Settings()
    state_storage = JsonFileStorage(file_path=settings.etl_state_storage)

    extractor = PostgresExtractor()
    transformator = DataTransform()
    loader = ElasticSearchLoader()

    extractor.connect()

    while True:
        sleep(30)  # elasticsearch starts slowly so sleep first
        data_transfer()
