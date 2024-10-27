"""Unittests for Humemai basic functions."""

import unittest
from datetime import datetime
from humemai.janusgraph import Humemai
from humemai.memory import (
    Memory,
    ShortMemory,
    LongMemory,
    EpisodicMemory,
    SemanticMemory,
)


class TestHumemaiWithMemory(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """Start containers, connect to Gremlin, and initialize Humemai instance."""
        cls.humemai = Humemai()
        cls.humemai.start_containers(warmup_seconds=20)
        cls.humemai.connect()
        cls.humemai.remove_all()
        cls.humemai.reset_memory_id()

    @classmethod
    def tearDownClass(cls) -> None:
        """Disconnect and stop containers after all tests."""
        cls.humemai.disconnect()
        cls.humemai.stop_containers()
        cls.humemai.remove_containers()

    def test_write_and_read_memory(self):
        """Test writing and reading a basic Memory instance."""
        memory = Memory(
            head_label="Person",
            tail_label="Company",
            edge_label="works_for",
            head_properties={"name": "Alice"},
            tail_properties={"name": "Acme Corp"},
            edge_properties={"since": "2020"},
        )

        # Write memory and read it back
        self.humemai.write_memory(memory)
        read_memory = self.humemai.read_memory(memory.memory_id)

        # Assertions to verify memory contents
        self.assertEqual(read_memory.head_label, memory.head_label)
        self.assertEqual(read_memory.tail_label, memory.tail_label)
        self.assertEqual(read_memory.edge_label, memory.edge_label)

        # Ensure head properties in `memory` are a subset of those in `read_memory`
        self.assertTrue(
            all(
                item in read_memory.head_properties.items()
                for item in memory.head_properties.items()
            ),
            "head_properties in `memory` are not a subset of `read_memory`",
        )

        # Ensure tail properties in `memory` are a subset of those in `read_memory`
        self.assertTrue(
            all(
                item in read_memory.tail_properties.items()
                for item in memory.tail_properties.items()
            ),
            "tail_properties in `memory` are not a subset of `read_memory`",
        )

        # Ensure edge properties in `memory` are a subset of those in `read_memory`
        self.assertTrue(
            all(
                item in read_memory.edge_properties.items()
                for item in memory.edge_properties.items()
            ),
            "edge_properties in `memory` are not a subset of `read_memory`",
        )

    def test_write_and_read_short_memory(self):
        """Test writing and reading a ShortMemory instance."""
        memory = ShortMemory(
            head_label="Person",
            tail_label="Company",
            edge_label="works_for",
            head_properties={"name": "Alice"},
            tail_properties={"name": "Acme Corp"},
            edge_properties={
                "since": "2020",
                "current_time": datetime.now().isoformat(),
            },
        )

        self.humemai.write_memory(memory)
        read_memory = self.humemai.read_memory(memory.memory_id)

        # Assertions for ShortMemory
        self.assertEqual(
            read_memory.edge_properties["current_time"],
            memory.edge_properties["current_time"],
        )

    def test_write_and_read_long_memory(self):
        """Test writing and reading a LongMemory instance."""
        memory = LongMemory(
            head_label="Person",
            tail_label="Company",
            edge_label="works_for",
            head_properties={"name": "Alice"},
            tail_properties={"name": "Acme Corp"},
            edge_properties={"since": "2020"},
        )

        self.humemai.write_memory(memory)
        read_memory = self.humemai.read_memory(memory.memory_id)

        # Assertions for LongMemory
        self.assertEqual(read_memory.edge_properties["num_recalled"], 0)

    def test_write_and_read_episodic_memory(self):
        """Test writing and reading an EpisodicMemory instance."""
        memory = EpisodicMemory(
            head_label="Person",
            tail_label="Company",
            edge_label="works_for",
            head_properties={"name": "Alice"},
            tail_properties={"name": "Acme Corp"},
            edge_properties={
                "event_time": datetime.now().isoformat(),
                "emotion": "sad",
                "location": "Office",
            },
        )

        self.humemai.write_memory(memory)
        read_memory = self.humemai.read_memory(memory.memory_id)

        # Assertions for EpisodicMemory
        self.assertEqual(
            read_memory.edge_properties["event_time"],
            memory.edge_properties["event_time"],
        )
        self.assertEqual(read_memory.edge_properties["emotion"], "sad")

    def test_write_and_read_semantic_memory(self):
        """Test writing and reading a SemanticMemory instance."""
        memory = SemanticMemory(
            head_label="Person",
            tail_label="Company",
            edge_label="works_for",
            head_properties={"name": "Alice"},
            tail_properties={"name": "Acme Corp"},
            edge_properties={
                "known_since": datetime.now().isoformat(),
                "derived_from": "HR",
            },
        )

        self.humemai.write_memory(memory)
        read_memory = self.humemai.read_memory(memory.memory_id)

        # Assertions for SemanticMemory
        self.assertEqual(
            read_memory.edge_properties["known_since"],
            memory.edge_properties["known_since"],
        )
        self.assertEqual(read_memory.edge_properties["derived_from"], "HR")

    def test_delete_memory(self):
        """Test deleting a memory based on memory_id."""
        memory = Memory(
            head_label="Person",
            tail_label="Company",
            edge_label="works_for",
            head_properties={"name": "Alice"},
            tail_properties={"name": "Acme Corp"},
            edge_properties={"since": "2020"},
        )

        self.humemai.write_memory(memory)
        self.humemai.delete_memory(memory.memory_id)

        # Verify memory deletion
        with self.assertRaises(Exception):
            self.humemai.read_memory(memory.memory_id)
