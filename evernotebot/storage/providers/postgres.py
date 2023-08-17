import json
import os
import typing
from typing import Dict, Optional

from dotenv import load_dotenv
import psycopg2


from evernotebot.storage.providers import BaseProvider


load_dotenv()


class PostgreSQL(BaseProvider):
    def __init__(self, dirpath: str = None, collection: str = None, db_name: str = None) -> None:
        self.database_url = os.getenv("DATABASE_URL", default=f'postgresql://postgres:mysecretpassword@localhost/{db_name}')

        self._connection = psycopg2.connect(self.database_url)
        self.cursor = self._connection.cursor()
        self._table_name = collection

        self.cursor.execute(f'CREATE TABLE IF NOT EXISTS {collection} (id SERIAL PRIMARY KEY, data TEXT)')
        self._connection.commit()

    def create(self, data: dict, auto_generate_id: bool = False) -> int:
        connection = psycopg2.connect(self.database_url)
        cursor = connection.cursor()

        if auto_generate_id:
            if 'id' in data:
                del data['id']
            cursor.execute(
                f'INSERT INTO {self._table_name} (data) VALUES (%s) RETURNING id;', (json.dumps(data), )
            )
        else:
            object_id = data['id']
            if object_id <= 0:
                raise Exception(f'Invalid id `{object_id}`. Id must be >= 0')
            self.cursor.execute(
                f'INSERT INTO {self._table_name} (id, data) VALUES (%s, %s) RETURNING id;', (object_id, json.dumps(data))
            )
        connection.commit()

        return cursor.fetchone()[0]

    def get(self, object_id: int, fail_if_not_exists: bool = False) -> Dict:
        query = object_id if isinstance(object_id, dict) else {'id': object_id}
        objects = self.get_all(query)
        result = list(objects)
        if fail_if_not_exists and not result:
            raise Exception(f'Object not found. Query: {query}')
        return result and result[0]

    def get_all(self, query: Optional[Dict] = None) -> typing.Generator:
        self.connection = psycopg2.connect(self.database_url)
        self.cursor = self.connection.cursor()

        if query is None:
            query = {}
        if 'id' in query:
            self.cursor.execute(f'SELECT id, data FROM {self._table_name} WHERE id = %s ', (query['id'],))
        else:
            self.cursor.execute(f'SELECT id, data FROM {self._table_name}')

        objects = self.cursor.fetchall()
        if not objects:
            return tuple()
        for object_id, json_data in objects:
            data = json.loads(json_data)
            data['id'] = object_id
            if self._check_query(data, query):
                yield data

    def _check_query(self, document: dict, query: dict) -> bool:
        matched = True
        for k, query_value in query.items():
            key_value = document
            for name in k.split('.'):
                key_value = key_value.get(name) if isinstance(key_value, dict) else None
                if key_value is None:
                    break
            if isinstance(query_value, dict):
                matched = self._check_query(key_value, query_value)
            else:
                matched = key_value == query_value
            if not matched:
                return False
        return matched

    def save(self, data: dict) -> int:
        self._connection = psycopg2.connect(self.database_url)
        self.cursor = self._connection.cursor()

        object_id = data['id']
        if not object_id:
            object_id = self.create(data, auto_generate_id=True)
        else:
            self.cursor.execute(
                f'UPDATE {self._table_name} SET data=%s WHERE id=%s RETURNING id;', (json.dumps(data), object_id)
            )
            self._connection.commit()
            if self.cursor.fetchone()[0] == 0:
                raise Exception(f'Object `{object_id}` not found')
        return object_id

    def delete(self, object_id: int, check_deleted_count: bool = True) -> None:
        self._connection = psycopg2.connect(self.database_url)
        self.cursor = self._connection.cursor()

        self.cursor.execute(f'DELETE FROM {self._table_name} WHERE id=%s RETURNING id;', (object_id,))
        self._connection.commit()

        if check_deleted_count and self.cursor.rowcount != 1:
            raise Exception(f'Object `{object_id}` not found')

    def close(self) -> None:
        try:
            self._connection.commit()
        except Exception:
            pass
        finally:
            self.cursor.close()
            self._connection.close()
