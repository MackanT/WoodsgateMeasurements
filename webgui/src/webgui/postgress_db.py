"""Database repository for water measurement data."""

import psycopg2
from psycopg2 import sql
from pathlib import Path
from datetime import datetime, date
import pandas as pd


class SensorDataRepository:
    """Repository class for accessing water measurement data from Postgress database."""

    def __init__(self, pwd_path: str | Path) -> None:
        """Initialize repository, reading and validating the database password.

        A new connection is opened per query (see `_query`) rather than kept
        open for the lifetime of the repository: this repository is a single
        module-level instance shared by every web request, and a single
        shared psycopg2 connection/cursor is not safe to use concurrently -
        two overlapping requests interleaving execute()/fetchall() calls on
        the same cursor can corrupt or mix up each other's results.

        Args:
            pwd_path: Path to file containing database password

        Raises:
            FileNotFoundError: If password file doesn't exist
        """
        self._password = self._read_password(str(pwd_path))
        # Fail fast on startup if the database is unreachable, rather than
        # only discovering it on the first page load.
        self._connect().close()

    @staticmethod
    def _read_password(pwd_file_name: str) -> str:
        """Read and validate the database password file.

        Args:
            pwd_file_name: Path to file containing database password

        Returns:
            The stripped password string

        Raises:
            FileNotFoundError: If password file doesn't exist
            ValueError: If password file is empty
        """
        pwd_path = Path(pwd_file_name)

        if not pwd_path.exists():
            raise FileNotFoundError(f"Password file not found: {pwd_file_name}")

        try:
            with open(pwd_file_name, "r") as f:
                pwd = f.readline()
        except IOError as e:
            raise IOError(f"Failed to read password file: {e}")

        pwd = pwd.strip()

        if not pwd:
            raise ValueError("Password file is empty")

        return pwd

    def _connect(self) -> psycopg2.extensions.connection:
        """Open a new PostgreSQL connection.

        Returns:
            A new connection

        Raises:
            psycopg2.OperationalError: If connection to database fails
            psycopg2.Error: For other database-related errors
        """
        try:
            return psycopg2.connect(
                host="192.168.1.177",
                database="sensor_data",
                user="admin",
                password=self._password,
                connect_timeout=10
            )
        except psycopg2.OperationalError as e:
            raise psycopg2.OperationalError(
                f"Failed to connect to PostgreSQL database at 192.168.1.177: {e}"
            ) from e
        except psycopg2.Error as e:
            raise psycopg2.Error(f"Database error during connection: {e}") from e

    def _query(
        self, query, params: tuple, default_columns: list[str] | None = None
    ) -> pd.DataFrame:
        """Run a query against a fresh connection and return the results as a DataFrame.

        Args:
            query: SQL query (str or psycopg2.sql.Composed)
            params: Query parameters
            default_columns: Column names to use for an empty DataFrame.
                           If None, uses cursor.description.

        Returns:
            DataFrame with fetched data or empty DataFrame with specified columns
        """
        # Note: psycopg2 connections only manage the transaction (commit/
        # rollback) as a context manager - they must still be closed
        # explicitly, otherwise every query here would leak a connection
        # just like the ADC file descriptor leak this was written to avoid.
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                if rows:
                    columns = [desc[0] for desc in cursor.description]
                    df = pd.DataFrame(rows, columns=columns)
                else:
                    cols = default_columns if default_columns else [
                        desc[0] for desc in cursor.description
                    ] if cursor.description else []
                    df = pd.DataFrame(columns=cols)
        finally:
            conn.close()
        return df

    def get_data_by_date_range(
        self, table_name: str, start_date: datetime | date, end_date: datetime | date
    ) -> pd.DataFrame:
        """Retrieve water measurement data for a date range.

        Args:
            start_date: Start date as datetime or date object
            end_date: End date as datetime or date object

        Returns:
            DataFrame with columns: timestamp, register, name, value
        """
        return self._get_data_by_date_range_internal(table_name, start_date, end_date)

    def get_data_by_datetime_range(
        self, table_name: str, start_datetime: datetime, end_datetime: datetime
    ) -> pd.DataFrame:
        """Retrieve water measurement data for a datetime range with precise time.

        Args:
            start_datetime: Start datetime object
            end_datetime: End datetime object

        Returns:
            DataFrame with columns: timestamp, register, name, value
        """
        return self._get_data_by_date_range_internal(table_name, start_datetime, end_datetime)

    def _get_data_by_date_range_internal(
        self, table_name: str, start_date: datetime | date, end_date: datetime | date
    ) -> pd.DataFrame:
        """Internal method to retrieve data by date range.

        Args:
            start_date: Start date/datetime
            end_date: End date/datetime

        Returns:
            DataFrame with columns: timestamp, register, name, value
        """
        # Convert to string format for SQL query
        if isinstance(start_date, datetime):
            start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(start_date, date):
            start_str = start_date.strftime("%Y-%m-%d")
        else:
            start_str = str(start_date)

        if isinstance(end_date, datetime):
            end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(end_date, date):
            # For date objects, include the full day by adding 23:59:59
            end_datetime = datetime.combine(
                end_date, datetime.max.time().replace(microsecond=0)
            )
            end_str = end_datetime.strftime("%Y-%m-%d %H:%M:%S")
        else:
            end_str = str(end_date)
        
        df = self._query(
            sql.SQL("select * from {} where timestamp between %s and %s").format(
                sql.Identifier(table_name)
            ),
            (start_str, end_str),
            default_columns=["timestamp", "register", "name", "value"],
        )

        # Convert timestamp column to datetime
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    def get_all_data(self, table_name: str) -> pd.DataFrame:
        """Retrieve all data from a specified table.

        Args:
            table_name: Name of the table to query

        Returns:
            DataFrame with columns: timestamp, register, name, value
        """
        df = self._query(
            sql.SQL("SELECT * FROM {} ORDER BY timestamp").format(
                sql.Identifier(table_name)
            ),
            (),
            default_columns=["timestamp", "register", "name", "value"],
        )

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        return df

    def get_latest_measurement(self, table_name: str) -> pd.DataFrame:
        """Retrieve the most recent measurement.

        Args:
            table_name: Name of the table to query

        Returns:
            DataFrame with the latest measurement or empty DataFrame if no data
        """
        df = self._query(
            sql.SQL("SELECT * FROM {} ORDER BY timestamp DESC LIMIT 1").format(
                sql.Identifier(table_name)
            ),
            (),
            default_columns=["timestamp", "register", "name", "value"],
        )

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        return df

    def get_latest_per_name(self, table_name: str) -> pd.DataFrame:
        """Retrieve the most recent row for each distinct `name` in a table.

        Useful for status cards, since these tables hold multiple named
        series (e.g. different temperature sensors) and a plain "most recent
        row overall" would only ever return whichever series happened to
        report last.

        Args:
            table_name: Name of the table to query

        Returns:
            DataFrame with one row per name, or empty DataFrame if no data
        """
        df = self._query(
            sql.SQL("SELECT DISTINCT ON (name) * FROM {} ORDER BY name, timestamp DESC").format(
                sql.Identifier(table_name)
            ),
            (),
            default_columns=["timestamp", "register", "name", "value"],
        )

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        return df

    def get_data_count(self, table_name: str) -> int:
        """Get the total count of measurements in the database.

        Args:
            table_name: Name of the table to query

        Returns:
            Number of measurement records
        """
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(
                        sql.Identifier(table_name)
                    )
                )
                count = cursor.fetchone()[0]
        finally:
            conn.close()

        return count
