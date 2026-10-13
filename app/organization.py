"""Organization hierarchy traversal and scoping module.
"""

from collections import deque
from typing import Optional, Set, Dict, List
import pandas as pd


class UnknownOrganizationError(Exception):
    """Raised when an organization unit ID does not exist in the hierarchy."""
    def __init__(self, org_id: str):
        super().__init__(f"Organization unit '{org_id}' not found.")
        self.org_id = org_id


class OrganizationHierarchy:
    """Manages the organization tree, cycle detection, and descendant resolution."""

    def __init__(self, org_units_df: pd.DataFrame):
        """Build the organization tree index from cleaned org_units DataFrame.

        Args:
            org_units_df: Cleaned DataFrame with 'org_id' and 'parent_id' columns.
        """
        self.known_orgs: Set[str] = set()
        self.children_map: Dict[str, List[str]] = {}
        self.parent_map: Dict[str, Optional[str]] = {}
        self._build_tree(org_units_df)

    def _build_tree(self, df: pd.DataFrame) -> None:
        """Parse DataFrame into parent-child adjacency lists with cycle defense."""
        if df.empty or "org_id" not in df.columns:
            return

        # Deduplicate org_id, keeping the first occurrence
        deduped = df.drop_duplicates(subset=["org_id"], keep="first")

        for _, row in deduped.iterrows():
            org_id = str(row["org_id"]).strip()
            if not org_id:
                continue

            self.known_orgs.add(org_id)
            if org_id not in self.children_map:
                self.children_map[org_id] = []

            parent_val = row.get("parent_id")
            parent_id: Optional[str] = None
            if pd.notna(parent_val):
                p_str = str(parent_val).strip()
                if p_str and p_str != org_id:  # guard against direct self-referencing
                    parent_id = p_str

            self.parent_map[org_id] = parent_id

        # Populate children_map
        for org_id, parent_id in self.parent_map.items():
            if parent_id and parent_id in self.known_orgs:
                self.children_map[parent_id].append(org_id)

    def get_descendants(self, root_org_id: str) -> Set[str]:
        """Return the root org ID and all of its descendant org IDs.

        Uses breadth-first search with visited tracking to safely handle cycles.

        Args:
            root_org_id: The organization unit ID to start traversal from.

        Returns:
            A set of organization IDs including root_org_id and all sub-units.

        Raises:
            UnknownOrganizationError: If root_org_id is not in known organizations.
        """
        clean_root = root_org_id.strip()
        if clean_root not in self.known_orgs:
            raise UnknownOrganizationError(clean_root)

        descendants: Set[str] = set()
        queue = deque([clean_root])
        visited: Set[str] = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            descendants.add(current)

            for child in self.children_map.get(current, []):
                if child not in visited:
                    queue.append(child)

        return descendants

    def get_scoped_person_ids(
        self,
        org_id: Optional[str],
        people_df: pd.DataFrame
    ) -> Set[str]:
        """Return distinct person_ids within scope of the given org_id (or all if None).

        Args:
            org_id: Root organization unit ID, or None/empty for company-wide.
            people_df: Cleaned people DataFrame with 'person_id' and 'org_id'.

        Returns:
            Set of unique person_ids eligible for metric calculations.
        """
        if people_df.empty or "person_id" not in people_df.columns:
            return set()

        if not org_id:
            # Company-wide: return all non-empty person IDs
            valid_people = people_df["person_id"].dropna().astype(str).str.strip()
            return set(valid_people[valid_people != ""].tolist())

        # Scoped to organization subtree
        descendant_orgs = self.get_descendants(org_id)
        if not descendant_orgs or "org_id" not in people_df.columns:
            return set()

        filtered_people = people_df[people_df["org_id"].astype(str).str.strip().isin(descendant_orgs)]
        valid_people = filtered_people["person_id"].dropna().astype(str).str.strip()
        return set(valid_people[valid_people != ""].tolist())
