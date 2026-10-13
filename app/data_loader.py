"""Configurable data loading and initialization layer.
"""

import os
from pathlib import Path
from typing import Optional, Dict
import pandas as pd

from app.data_cleaner import DataCleaner
from app.organization import OrganizationHierarchy


class DataLoaderError(Exception):
    """Raised when critical dataset loading or validation fails."""
    pass


class DatasetContainer:
    """Immutable container holding cleaned datasets, organization hierarchy, and cleaner issues."""

    def __init__(
        self,
        org_units_df: pd.DataFrame,
        people_df: pd.DataFrame,
        price_list_df: pd.DataFrame,
        seats_df: pd.DataFrame,
        activity_events_df: pd.DataFrame,
        cleaner: DataCleaner
    ):
        self.org_units_df = org_units_df
        self.people_df = people_df
        self.price_list_df = price_list_df
        self.seats_df = seats_df
        self.activity_events_df = activity_events_df
        self.cleaner = cleaner
        self.hierarchy = OrganizationHierarchy(org_units_df)


class DataLoader:
    """Manages reading, parsing, cleaning, and validating CSV datasets."""

    def __init__(self, data_dir: Optional[str] = None):
        """Initialize loader with a directory path or use environment variable DATA_DIR or 'data'."""
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        else:
            env_dir = os.getenv("DATA_DIR", "data")
            self.data_dir = Path(env_dir)

        self._container: Optional[DatasetContainer] = None

    def is_loaded(self) -> bool:
        """Check if container is successfully loaded and validated."""
        return self._container is not None

    def get_container(self) -> DatasetContainer:
        """Get the active dataset container."""
        if self._container is None:
            raise DataLoaderError("Datasets have not been loaded yet.")
        return self._container

    def load_from_directory(self) -> DatasetContainer:
        """Load all 5 CSV files from self.data_dir and clean them.

        Raises:
            DataLoaderError: If any required CSV file is missing or unreadable.
        """
        required_files = {
            "org_units": "org_units.csv",
            "people": "people.csv",
            "price_list": "price_list.csv",
            "seats": "seats.csv",
            "activity_events": "activity_events.csv"
        }

        missing_files = []
        for name, filename in required_files.items():
            filepath = self.data_dir / filename
            if not filepath.is_file():
                missing_files.append(str(filepath))

        if missing_files:
            raise DataLoaderError(
                f"Missing required CSV dataset files in '{self.data_dir}': {', '.join(missing_files)}"
            )

        try:
            raw_org_units = pd.read_csv(self.data_dir / "org_units.csv", dtype=str)
            raw_people = pd.read_csv(self.data_dir / "people.csv", dtype=str)
            raw_price_list = pd.read_csv(self.data_dir / "price_list.csv")
            raw_seats = pd.read_csv(self.data_dir / "seats.csv", dtype=str)
            raw_activity_events = pd.read_csv(self.data_dir / "activity_events.csv", dtype=str)
        except Exception as exc:
            raise DataLoaderError(f"Error reading CSV files: {str(exc)}") from exc

        return self.load_from_dataframes(
            raw_org_units=raw_org_units,
            raw_people=raw_people,
            raw_price_list=raw_price_list,
            raw_seats=raw_seats,
            raw_activity_events=raw_activity_events
        )

    def load_from_dataframes(
        self,
        raw_org_units: pd.DataFrame,
        raw_people: pd.DataFrame,
        raw_price_list: pd.DataFrame,
        raw_seats: pd.DataFrame,
        raw_activity_events: pd.DataFrame
    ) -> DatasetContainer:
        """Clean and validate raw DataFrames, storing the result in self._container."""
        cleaner = DataCleaner()

        # Step 1: Clean org units
        clean_org_units = cleaner.clean_org_units(raw_org_units)
        valid_org_ids = set(clean_org_units["org_id"].unique())

        # Step 2: Clean people
        clean_people = cleaner.clean_people(raw_people, valid_org_ids=valid_org_ids)
        valid_person_ids = set(clean_people["person_id"].unique())

        # Step 3: Clean price list
        clean_price_list = cleaner.clean_price_list(raw_price_list)

        # Step 4: Clean seats
        clean_seats = cleaner.clean_seats(raw_seats, valid_person_ids=valid_person_ids)

        # Step 5: Clean activity events
        clean_activity_events = cleaner.clean_activity_events(raw_activity_events, valid_person_ids=valid_person_ids)

        self._container = DatasetContainer(
            org_units_df=clean_org_units,
            people_df=clean_people,
            price_list_df=clean_price_list,
            seats_df=clean_seats,
            activity_events_df=clean_activity_events,
            cleaner=cleaner
        )
        return self._container
