# TODO: the file is deprecated and used only as a reference to how it should be for all other storages
import json
import os
from os.path import exists
import sqlite3
import typing
from typing import Dict, Optional

from dotenv import load_dotenv
import psycopg2

load_dotenv()


class Sqlite:
    def __init__(self, dirpath: str, *, collection: str = None, db_name: str = None) -> None:
        if not exists(dirpath):
            os.makedirs(dirpath)
        db_filepath = f'{dirpath}/{db_name}'
        self._connection = sqlite3.connect(db_filepath)
        self._table_name = collection
        self.__execute_sql(
            f'CREATE TABLE IF NOT EXISTS {collection}'
            '(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT)'
        )

    def __execute_sql(self, sql: str, *args) -> sqlite3.Cursor:
        sql = sql.strip().upper()
        cursor = self._connection.execute(sql, args)
        if not sql.startswith('SELECT'):
            self._connection.commit()
        return cursor

    def create(self, data: dict, auto_generate_id: bool = False) -> int:
        table = self._table_name
        if auto_generate_id:
            if 'id' in data:
                del data['id']
            sql = f'INSERT INTO {table}(data) VALUES(?)'
            cursor = self.__execute_sql(sql, json.dumps(data))
        else:
            object_id = data['id']
            if object_id <= 0:
                raise Exception(f'Invalid id `{object_id}`. Id must be >= 0')
            cursor = self.__execute_sql(f'INSERT INTO {table}(id, data) VALUES(?, ?)',
                                        object_id, json.dumps(data))
        return cursor.lastrowid

    def get(self, object_id: int, fail_if_not_exists: bool = False) -> Dict:
        query = object_id if isinstance(object_id, dict) else {'id': object_id}
        objects = self.get_all(query)
        result = list(objects)
        if fail_if_not_exists and not result:
            raise Exception(f'Object not found. Query: {query}')
        return result and result[0]

    def get_all(self, query: Optional[Dict] = None) -> typing.Generator:
        if query is None:
            query = {}
        table = self._table_name
        args = tuple()
        if 'id' in query:
            sql = f'SELECT id, data FROM {table} WHERE id=?'
            args = (query['id'],)
        else:
            sql = f'SELECT id, data FROM {table}'
        cursor = self.__execute_sql(sql, *args)
        objects = cursor.fetchall()
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
        object_id = data['id']
        if not object_id:
            object_id = self.create(data, auto_generate_id=True)
        else:
            table = self._table_name
            sql = f'UPDATE {table} SET data=? WHERE id=?'
            cursor = self.__execute_sql(sql, json.dumps(data), object_id)
            if cursor.rowcount == 0:
                raise Exception(f'Object `{object_id}` not found')
        return object_id

    def delete(self, object_id: int, check_deleted_count: bool = True) -> None:
        table = self._table_name
        sql = f'DELETE FROM {table} WHERE id=?'
        cursor = self.__execute_sql(sql, object_id)
        if check_deleted_count and cursor.rowcount != 1:
            raise Exception(f'Object `{object_id}` not found')

    def close(self) -> None:
        try:
            self._connection.commit()
        except Exception:
            pass
        finally:
            self._connection.close()


class PostgreSQL:
    def __init__(self, collection: str = None, db_name: str = None) -> None:
        database_url = os.getenv("DATABASE_URL", default=f'postgresql://postgres:mysecretpassword@localhost/{db_name}')

        self._connection = psycopg2.connect(database_url)
        self.cursor = self._connection.cursor()
        self._table_name = collection

        self.cursor.execute(f'CREATE TABLE IF NOT EXISTS {collection} (id SERIAL PRIMARY KEY, data TEXT)')
        self._connection.commit()

    def create(self, data: dict, auto_generate_id: bool = False) -> int:
        if auto_generate_id:
            if 'id' in data:
                del data['id']
            self.cursor.execute(
                f'INSERT INTO {self._table_name} (data) VALUES (%s) RETURNING id;', (json.dumps(data), )
            )
            self._connection.commit()
        else:
            object_id = data['id']
            if object_id <= 0:
                raise Exception(f'Invalid id `{object_id}`. Id must be >= 0')
            self.cursor.execute(
                f'INSERT INTO {self._table_name} (id, data) VALUES (%s, %s) RETURNING id;', (object_id, json.dumps(data))
            )
            self._connection.commit()

        return self.cursor.fetchone()[0]

    def get(self, object_id: int, fail_if_not_exists: bool = False) -> Dict:
        query = object_id if isinstance(object_id, dict) else {'id': object_id}
        objects = self.get_all(query)
        result = list(objects)
        if fail_if_not_exists and not result:
            raise Exception(f'Object not found. Query: {query}')
        return result and result[0]

    def get_all(self, query: Optional[Dict] = None) -> typing.Generator:
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
