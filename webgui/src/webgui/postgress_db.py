"""Database repository for water measurement data."""

from typing import Tuple
import psycopg2
from psycopg2 import sql
from pathlib import Path
from datetime import datetime, date
import pandas as pd


class SensorDataRepository:
    """Repository class for accessing water measurement data from Postgress database."""

    def __init__(self, pwd_path: str | Path) -> None:
        """Initialize repository with PostgreSQL connection.

        Args:
            pwd_path: Path to file containing database password
            
        Raises:
            FileNotFoundError: If password file doesn't exist
            psycopg2.Error: If database connection fails
        """
        
        self.conn, self.cursor = self._connect_db(pwd_file_name=str(pwd_path))
        

    def _connect_db(
        self, pwd_file_name: str,
    ) -> Tuple[psycopg2.extensions.connection, psycopg2.extensions.cursor]:
        """Connect to PostgreSQL database.
        
        Args:
            pwd_file_name: Path to file containing database password
            
        Returns:
            Tuple of (connection, cursor)
            
        Raises:
            FileNotFoundError: If password file doesn't exist
            psycopg2.OperationalError: If connection to database fails
            psycopg2.Error: For other database-related errors
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

        try:
            conn = psycopg2.connect(
                host="192.168.1.177", 
                database="sensor_data", 
                user="admin", 
                password=pwd,
                connect_timeout=10
            )
            cursor = conn.cursor()
            return conn, cursor
        except psycopg2.OperationalError as e:
            raise psycopg2.OperationalError(
                f"Failed to connect to PostgreSQL database at 192.168.1.177: {e}"
            ) from e
        except psycopg2.Error as e:
            raise psycopg2.Error(f"Database error during connection: {e}") from e

    def _cursor_to_df(self, default_columns: list[str] | None = None) -> pd.DataFrame:
        """Convert cursor results to pandas DataFrame.
        
        Args:
            default_columns: Column names to use for empty DataFrame. 
                           If None, uses cursor.description.
        
        Returns:
            DataFrame with fetched data or empty DataFrame with specified columns
        """
        rows = self.cursor.fetchall()
        if rows:
            columns = [desc[0] for desc in self.cursor.description]
            df = pd.DataFrame(rows, columns=columns)
        else:
            cols = default_columns if default_columns else [
                desc[0] for desc in self.cursor.description
            ] if self.cursor.description else []
            df = pd.DataFrame(columns=cols)
        return df

    def close(self) -> None:
        """Close database connection and cursor."""
        if hasattr(self, 'cursor') and self.cursor:
            self.cursor.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes connection."""
        self.close()
        return False

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
        
        self.cursor.execute(
            sql.SQL("select * from {} where timestamp between %s and %s").format(
                sql.Identifier(table_name)
            ),
            (start_str, end_str),
        )
        
        df = self._cursor_to_df(default_columns=["timestamp", "register", "name", "value"])
        
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
        self.cursor.execute(
            sql.SQL("SELECT * FROM {} ORDER BY timestamp").format(
                sql.Identifier(table_name)
            )
        )
        
        df = self._cursor_to_df(default_columns=["timestamp", "register", "name", "value"])
        
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
        self.cursor.execute(
            sql.SQL("SELECT * FROM {} ORDER BY timestamp DESC LIMIT 1").format(
                sql.Identifier(table_name)
            )
        )
        
        df = self._cursor_to_df(default_columns=["timestamp", "register", "name", "value"])
        
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
        self.cursor.execute(
            sql.SQL("SELECT COUNT(*) FROM {}").format(
                sql.Identifier(table_name)
            )
        )
        count = self.cursor.fetchone()[0]

        return count
