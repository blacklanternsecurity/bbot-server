"""Tests for the index diff computation logic (pure, no MongoDB required)."""

from bbot_server.applets.base import BaseApplet


class TestComputeIndexDiff:
    """Tests for _compute_index_diff static method."""

    def test_no_diff_when_identical(self):
        """If desired and existing match exactly, diff should be empty."""
        existing = {
            "field_1": {"key": [("field", 1)], "unique": True, "sparse": True},
            "other_1": {"key": [("other", 1)], "unique": False, "sparse": False},
        }
        desired = {
            "field_1": {"key": [("field", 1)], "unique": True, "sparse": True},
            "other_1": {"key": [("other", 1)], "unique": False, "sparse": False},
        }

        diff = BaseApplet._compute_index_diff(desired, set(), existing, set())

        assert diff["drop"] == []
        assert diff["create"] == []
        assert diff["drop_text"] is False
        assert diff["create_text"] is None

    def test_drop_removed_index(self):
        """Index in existing but not in desired should be dropped."""
        existing = {
            "keep_1": {"key": [("keep", 1)], "unique": False, "sparse": False},
            "remove_1": {"key": [("remove", 1)], "unique": False, "sparse": False},
        }
        desired = {
            "keep_1": {"key": [("keep", 1)], "unique": False, "sparse": False},
        }

        diff = BaseApplet._compute_index_diff(desired, set(), existing, set())

        assert "remove_1" in diff["drop"]
        assert "keep_1" not in diff["drop"]

    def test_create_new_index(self):
        """Index in desired but not in existing should be created."""
        existing = {}
        desired = {
            "new_1": {"key": [("new", 1)], "unique": True, "sparse": True},
        }

        diff = BaseApplet._compute_index_diff(desired, set(), existing, set())

        assert len(diff["create"]) == 1
        assert diff["create"][0]["name"] == "new_1"
        assert diff["create"][0]["unique"] is True

    def test_recreate_when_unique_changes(self):
        """If unique option changes, index should be dropped and recreated."""
        existing = {
            "field_1": {"key": [("field", 1)], "unique": False, "sparse": False},
        }
        desired = {
            "field_1": {"key": [("field", 1)], "unique": True, "sparse": True},
        }

        diff = BaseApplet._compute_index_diff(desired, set(), existing, set())

        assert "field_1" in diff["drop"]
        assert any(c["name"] == "field_1" for c in diff["create"])

    def test_recreate_when_sparse_changes(self):
        """If sparse option changes, index should be dropped and recreated."""
        existing = {
            "field_1": {"key": [("field", 1)], "unique": True, "sparse": False},
        }
        desired = {
            "field_1": {"key": [("field", 1)], "unique": True, "sparse": True},
        }

        diff = BaseApplet._compute_index_diff(desired, set(), existing, set())

        assert "field_1" in diff["drop"]
        assert any(c["name"] == "field_1" for c in diff["create"])

    def test_recreate_when_key_changes(self):
        """If key structure changes, index should be dropped and recreated."""
        existing = {
            "compound_1_a_1": {"key": [("compound", 1), ("a", 1)], "unique": True, "sparse": False},
        }
        desired = {
            "compound_1_a_1": {"key": [("compound", 1), ("b", 1)], "unique": True, "sparse": False},
        }

        diff = BaseApplet._compute_index_diff(desired, set(), existing, set())

        assert "compound_1_a_1" in diff["drop"]
        assert any(c["name"] == "compound_1_a_1" for c in diff["create"])

    def test_text_index_no_change(self):
        """If text fields are identical, no text index changes."""
        diff = BaseApplet._compute_index_diff({}, {"a", "b"}, {}, {"a", "b"})

        assert diff["drop_text"] is False
        assert diff["create_text"] is None

    def test_text_index_add_field(self):
        """Adding a text field should recreate text index."""
        diff = BaseApplet._compute_index_diff({}, {"a", "b"}, {}, {"a"})

        assert diff["drop_text"] is True
        assert diff["create_text"] == ["a", "b"]

    def test_text_index_remove_field(self):
        """Removing a text field should recreate text index."""
        diff = BaseApplet._compute_index_diff({}, {"a"}, {}, {"a", "b"})

        assert diff["drop_text"] is True
        assert diff["create_text"] == ["a"]

    def test_text_index_create_from_nothing(self):
        """Creating text index when none exists."""
        diff = BaseApplet._compute_index_diff({}, {"a"}, {}, set())

        assert diff["drop_text"] is False
        assert diff["create_text"] == ["a"]

    def test_text_index_drop_entirely(self):
        """Dropping text index when no longer desired."""
        diff = BaseApplet._compute_index_diff({}, set(), {}, {"a"})

        assert diff["drop_text"] is True
        assert diff["create_text"] is None

    def test_idempotent_second_run(self):
        """Running diff twice with same state should produce empty diff."""
        # Simulate first run: build desired from "model"
        desired = {
            "host_1": {"key": [("host", 1)], "unique": False, "sparse": False},
            "id_1": {"key": [("id", 1)], "unique": True, "sparse": True},
        }
        desired_text = {"description", "name"}

        # After first run, existing should match desired
        existing = {
            "host_1": {"key": [("host", 1)], "unique": False, "sparse": False},
            "id_1": {"key": [("id", 1)], "unique": True, "sparse": True},
        }
        existing_text = {"description", "name"}

        diff = BaseApplet._compute_index_diff(desired, desired_text, existing, existing_text)

        assert diff["drop"] == []
        assert diff["create"] == []
        assert diff["drop_text"] is False
        assert diff["create_text"] is None
