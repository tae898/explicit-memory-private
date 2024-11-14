"""Unittests for Humemai memory retrieval functions."""

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


class TestHumemaiGetMemories(unittest.TestCase):
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

    def test_get_all_short_term_memories(self):
        """Test retrieval of all short-term memories."""
        # Create a ShortMemory instance and write to database
        self.humemai.remove_all()
        self.humemai.reset_memory_id()

        short_memory = ShortMemory(
            head_label="Person",
            tail_label="Object",
            edge_label="owns",
            head_properties={"name": "Alice"},
            tail_properties={"item": "Book"},
            edge_properties={
                "current_time": datetime.now().isoformat(timespec="seconds")
            },
        )
        self.humemai.write_memory(short_memory)
        self.humemai.write_memory(short_memory)

        # Retrieve all short-term memories
        retrieved_short_memories = self.humemai.get_all_short_term_memories()

        # Verify that at least one ShortMemory was retrieved
        self.assertEqual(len(retrieved_short_memories), 2)
        self.assertEqual(self.humemai.count_short_term_memories(), 2)

        for memory in retrieved_short_memories:
            self.assertIsInstance(memory, ShortMemory)
            self.assertEqual(memory.head_label, "Person")
            self.assertEqual(memory.tail_label, "Object")

    def test_get_all_episodic_memories(self):
        """Test retrieval of all episodic memories."""
        # Create an EpisodicMemory instance and write to database
        self.humemai.remove_all()
        self.humemai.reset_memory_id()

        episodic_memory = EpisodicMemory(
            head_label="Person",
            tail_label="Event",
            edge_label="attended",
            head_properties={"name": "Bob"},
            tail_properties={"event_name": "Concert"},
            edge_properties={
                "event_time": datetime.now().isoformat(timespec="seconds")
            },
        )
        self.humemai.write_memory(episodic_memory)
        self.humemai.write_memory(episodic_memory)
        self.humemai.write_memory(episodic_memory)

        # Retrieve all episodic memories
        retrieved_episodic_memories = self.humemai.get_all_episodic_memories()

        # Verify that at least one EpisodicMemory was retrieved
        self.assertEqual(len(retrieved_episodic_memories), 3)
        self.assertEqual(self.humemai.count_episodic_memories(), 3)

        for memory in retrieved_episodic_memories:
            self.assertIsInstance(memory, EpisodicMemory)
            self.assertEqual(memory.head_label, "Person")
            self.assertEqual(memory.tail_label, "Event")

    def test_get_all_semantic_memories(self):
        """Test retrieval of all semantic memories."""
        # Create a SemanticMemory instance and write to database
        self.humemai.remove_all()
        self.humemai.reset_memory_id()

        semantic_memory = SemanticMemory(
            head_label="Concept",
            tail_label="Fact",
            edge_label="is_related_to",
            head_properties={"concept_name": "Gravity"},
            tail_properties={"fact_detail": "Attracts objects"},
            edge_properties={
                "known_since": datetime.now().isoformat(timespec="seconds"),
                "derived_from": "Physics",
            },
        )
        self.humemai.write_memory(semantic_memory)

        # Retrieve all semantic memories
        retrieved_semantic_memories = self.humemai.get_all_semantic_memories()

        # Verify that at least one SemanticMemory was retrieved
        self.assertEqual(len(retrieved_semantic_memories), 1)
        self.assertEqual(self.humemai.count_semantic_memories(), 1)

        for memory in retrieved_semantic_memories:
            self.assertIsInstance(memory, SemanticMemory)
            self.assertEqual(memory.head_label, "Concept")
            self.assertEqual(memory.tail_label, "Fact")

    def test_get_all_long_term_memories(self):
        """Test retrieval of all long-term memories."""

        self.humemai.remove_all()
        self.humemai.reset_memory_id()

        mem = Memory(
            head_label="Person",
            tail_label="Company",
            edge_label="works_for",
            head_properties={"name": "Alice"},
            tail_properties={"name": "Acme Corp"},
            edge_properties={"since": "2020"},
        )

        self.humemai.write_memory(mem)
        self.humemai.write_memory(mem)

        mem = ShortMemory(
            head_label="Person",
            tail_label="Company",
            edge_label="works_for",
            head_properties={"name": "Alice"},
            tail_properties={"name": "Acme Corp"},
            edge_properties={"since": "2020", "current_time": "2024-10-27T11:51:06"},
        )
        self.humemai.write_memory(mem)

        mem = LongMemory(
            head_label="Person",
            tail_label="Company",
            edge_label="works_for",
            head_properties={"name": "Alice"},
            tail_properties={"name": "Acme Corp"},
            edge_properties={"since": "2020", "event_time": "2024-10-27T11:51:06"},
        )
        self.humemai.write_memory(mem)
        self.humemai.write_memory(mem)
        self.humemai.write_memory(mem)

        mem = EpisodicMemory(
            head_label="Person",
            tail_label="Company",
            edge_label="works_for",
            head_properties={"name": "Alice"},
            tail_properties={"name": "Acme Corp"},
            edge_properties={"event_time": "2024-10-27T11:51:06", "emotion": "sad"},
        )
        self.humemai.write_memory(mem)

        mem = SemanticMemory(
            head_label="Person",
            tail_label="Company",
            edge_label="works_for",
            head_properties={"name": "Alice"},
            tail_properties={"name": "Acme Corp"},
            edge_properties={
                "known_since": "2024-10-27T11:51:06",
                "derived_from": "HR",
            },
        )
        self.humemai.write_memory(mem)
        self.humemai.write_memory(mem)

        # Retrieve all long-term memories
        retrieved_long_term_memories = self.humemai.get_all_long_term_memories()

        # Verify that exactly four long-term memories were retrieved
        self.assertEqual(len(retrieved_long_term_memories), 6)
        self.assertEqual(self.humemai.count_long_term_memories(), 6)

        # Verify that each memory is an instance of LongMemory or its subclasses
        for memory in retrieved_long_term_memories:
            self.assertIsInstance(memory, LongMemory)

        retrieved_all_memories = self.humemai.get_all_memories()
        self.assertEqual(len(retrieved_all_memories), 9)
        self.assertEqual(self.humemai.count_all_memories(), 9)
