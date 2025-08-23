"""Database repository for water measurement data."""

import sqlite3
from pathlib import Path
from datetime import datetime, date
import pandas as pd


class WaterDataRepository:
    """Repository class for accessing water measurement data from SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize repository with database path.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file not found: {self.db_path}")

    def get_data_by_date_range(
        self, start_date: datetime | date, end_date: datetime | date
    ) -> pd.DataFrame:
        """Retrieve water measurement data for a date range.

        Args:
            start_date: Start date as datetime or date object
            end_date: End date as datetime or date object

        Returns:
            DataFrame with columns: time, level, volume
        """
        return self._get_data_by_date_range_internal(start_date, end_date)

    def get_data_by_datetime_range(
        self, start_datetime: datetime, end_datetime: datetime
    ) -> pd.DataFrame:
        """Retrieve water measurement data for a datetime range with precise time.

        Args:
            start_datetime: Start datetime object
            end_datetime: End datetime object

        Returns:
            DataFrame with columns: time, level, volume
        """
        return self._get_data_by_date_range_internal(start_datetime, end_datetime)

    def _get_data_by_date_range_internal(
        self, start_date: datetime | date, end_date: datetime | date
    ) -> pd.DataFrame:
        """Internal method to retrieve data by date range.

        Args:
            start_date: Start date/datetime
            end_date: End date/datetime

        Returns:
            DataFrame with columns: time, level, volume
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

        with sqlite3.connect(self.db_path) as con:
            df = pd.read_sql_query(
                "SELECT time, level, volume FROM data WHERE time BETWEEN ? AND ?",
                con,
                params=(start_str, end_str),
            )

        # Convert time column to datetime
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"])

        return df

    def get_all_data(self) -> pd.DataFrame:
        """Retrieve all water measurement data.

        Returns:
            DataFrame with columns: time, level, volume
        """
        with sqlite3.connect(self.db_path) as con:
            df = pd.read_sql_query(
                "SELECT time, level, volume FROM data ORDER BY time",
                con,
            )

        # Convert time column to datetime
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"])

        return df

    def get_latest_measurement(self) -> pd.DataFrame:
        """Retrieve the most recent water measurement.

        Returns:
            DataFrame with the latest measurement or empty DataFrame if no data
        """
        with sqlite3.connect(self.db_path) as con:
            df = pd.read_sql_query(
                "SELECT time, level, volume FROM data ORDER BY time DESC LIMIT 1",
                con,
            )

        # Convert time column to datetime
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"])

        return df

    def get_data_count(self) -> int:
        """Get the total count of measurements in the database.

        Returns:
            Number of measurement records
        """
        with sqlite3.connect(self.db_path) as con:
            cursor = con.cursor()
            cursor.execute("SELECT COUNT(*) FROM data")
            count = cursor.fetchone()[0]

        return count

    def test_date_conversion(self, test_date: datetime | date) -> str:
        """Test method to verify date conversion works correctly.

        Args:
            test_date: Date or datetime object to test

        Returns:
            String representation of how the date would be formatted for SQL
        """
        if isinstance(test_date, datetime):
            return test_date.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(test_date, date):
            end_datetime = datetime.combine(
                test_date, datetime.max.time().replace(microsecond=0)
            )
            return end_datetime.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return str(test_date)
