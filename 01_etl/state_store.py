import abc
import json
import logging


class BaseStorage:
    @abc.abstractmethod
    def save_state(self, state: dict) -> None:
        """Сохранить состояние в постоянное хранилище"""
        pass

    @abc.abstractmethod
    def retrieve_state(self) -> dict:
        """Загрузить состояние локально из постоянного хранилища"""
        pass


class JsonFileStorage(BaseStorage):
    """Writer and loader of etl state in json file format."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def save_state(self, state: dict) -> None:
        print(f'we are trying to save state: {state}')
        with open(self.file_path, 'w') as stor_file:
            json.dump(fp=stor_file, obj=state)

    def retrieve_state(self) -> dict:
        with open(self.file_path, 'r') as stor_file:
            try:
                return json.load(stor_file)
            except json.decoder.JSONDecodeError:
                return {}


class State:
    """
    Класс для хранения состояния при работе с данными, чтобы постоянно не перечитывать данные с начала.
    Здесь представлена реализация с сохранением состояния в файл.
    В целом ничего не мешает поменять это поведение на работу с БД или распределённым хранилищем.
    """

    def __init__(self, storage: BaseStorage) -> None:
        self.storage = storage

    def set_state(self, key: str, value: str) -> None:
        """Установить состояние для определённого ключа"""
        self.storage.save_state({key: value})

    def get_state(self, key: str) -> str:
        """Получить состояние по определённому ключу"""
        try:
            return self.storage.retrieve_state().get(key, '1970-01-01')
        except Exception:
            return '1970-01-01'


if __name__ == '__main__':
    stor = JsonFileStorage(file_path='json_storage.json')
    stat = State(stor)
    logging.info(stat.get_state(key='modified'))
    stat.set_state(key='modified', value='today')
    logging.info(stat.get_state(key='modified'))
