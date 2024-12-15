import sqlite3
from typing import List, Tuple, Any

class SQLiteManager:
    def __init__(self, db_name: str):
        """Initialize the SQLiteManager with the specified database name."""
        self.db_name = db_name

    def _connect(self):
        """Create a connection to the SQLite database."""
        return sqlite3.connect(self.db_name)

    def execute(self, sql: str, params: Tuple[Any, ...] = ()) -> None:
        """
        Execute an SQL command that doesn't return data (e.g., CREATE, INSERT, UPDATE, DELETE).
        :param sql: The SQL command to execute.
        :param params: Parameters for the SQL command.
        """
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                conn.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")

    def fetchall(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Tuple[Any, ...]]:
        """
        Execute an SQL command that returns data (e.g., SELECT).
        :param sql: The SQL query to execute.
        :param params: Parameters for the SQL query.
        :return: A list of tuples containing the query results.
        """
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            return []

    def create_table(self, table_name: str, columns: List[Tuple[str, str]]) -> None:
        """
        Create a table in the database.
        :param table_name: Name of the table to create.
        :param columns: A list of tuples specifying column names and types.
        """
        columns_definition = ", ".join(f"{name} {dtype}" for name, dtype in columns)
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_definition})"
        self.execute(sql)

    def insert(self, table_name: str, values: Tuple[Any, ...]) -> None:
        """
        Insert a record into a table.
        :param table_name: Name of the table to insert into.
        :param values: Tuple of values to insert.
        """
        placeholders = ", ".join("?" for _ in values)
        sql = f"INSERT INTO {table_name} VALUES ({placeholders})"
        self.execute(sql, values)

    def update(self, table_name: str, updates: str, condition: str, params: Tuple[Any, ...]) -> None:
        """
        Update records in a table.
        :param table_name: Name of the table to update.
        :param updates: Column updates (e.g., "column1 = ?, column2 = ?").
        :param condition: WHERE clause condition (e.g., "id = ?").
        :param params: Parameters for the SQL command.
        """
        sql = f"UPDATE {table_name} SET {updates} WHERE {condition}"
        self.execute(sql, params)

    def delete(self, table_name: str, condition: str, params: Tuple[Any, ...]) -> None:
        """
        Delete records from a table.
        :param table_name: Name of the table to delete from.
        :param condition: WHERE clause condition (e.g., "id = ?").
        :param params: Parameters for the SQL command.
        """
        sql = f"DELETE FROM {table_name} WHERE {condition}"
        self.execute(sql, params)