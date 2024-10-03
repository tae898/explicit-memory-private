import unittest
from datetime import datetime
from rdflib import URIRef, Literal, Namespace, RDF
from humemai import MemorySystem


class TestMemorySystem(unittest.TestCase):

    def setUp(self):
        # Initialize the memory system
        self.memory = MemorySystem()

        # Define multiple triples
        self.triples = [
            (
                URIRef("https://example.org/person/Alice"),
                URIRef("https://example.org/event/met"),
                URIRef("https://example.org/person/Bob"),
            ),
            (
                URIRef("https://example.org/person/Bob"),
                URIRef("https://example.org/event/met"),
                URIRef("https://example.org/person/Charlie"),
            ),
            (
                URIRef("https://example.org/person/Alice"),
                URIRef("https://example.org/relationship/knows"),
                URIRef("https://example.org/person/David"),
            ),
            (
                URIRef("https://example.org/person/Charlie"),
                URIRef("https://example.org/event/met"),
                URIRef("https://example.org/person/Eve"),
            ),
            (
                URIRef("https://example.org/person/David"),
                URIRef("https://example.org/event/invited"),
                URIRef("https://example.org/person/Alice"),
            ),
            (
                URIRef("https://example.org/person/Eve"),
                URIRef("https://example.org/relationship/worksWith"),
                URIRef("https://example.org/person/Bob"),
            ),
            (
                URIRef("https://example.org/person/Charlie"),
                URIRef("https://example.org/event/attended"),
                URIRef("https://example.org/person/Bob"),
            ),
            (
                URIRef("https://example.org/entity/Dog"),
                URIRef("https://example.org/relationship/is"),
                URIRef("https://example.org/entity/Animal"),
            ),
            (
                URIRef("https://example.org/person/Alice"),
                URIRef("https://example.org/relationship/owns"),
                URIRef("https://example.org/entity/Dog"),
            ),
            (
                URIRef("https://example.org/person/Eve"),
                URIRef("https://example.org/event/met"),
                URIRef("https://example.org/person/Alice"),
            ),
            (
                URIRef("https://example.org/person/John"),
                URIRef("https://example.org/relationship/loves"),
                URIRef("https://example.org/entity/Animal"),
            ),
        ]

        # Define qualifiers for episodic memories
        episodic_qualifiers_1 = {
            "location": "New York",
            "time": "2024-04-27T15:00:00",
            "emotion": "happy",
            "event": "Coffee meeting",
        }
        episodic_qualifiers_2 = {
            "location": "London",
            "time": "2024-05-01T10:00:00",
            "emotion": "excited",
            "event": "Conference meeting",
        }
        episodic_qualifiers_3 = {
            "location": "Paris",
            "time": "2024-05-03T14:00:00",
            "emotion": "curious",
            "event": "Workshop",
        }

        # Add episodic memories
        self.memory.memory.add_long_term_memory(
            "episodic", [self.triples[0]], **episodic_qualifiers_1
        )
        self.memory.memory.add_long_term_memory(
            "episodic", [self.triples[1]], **episodic_qualifiers_2
        )
        self.memory.memory.add_long_term_memory(
            "episodic", [self.triples[2]], **episodic_qualifiers_3
        )
        self.memory.memory.add_long_term_memory(
            "episodic", [self.triples[3]], **episodic_qualifiers_1
        )
        self.memory.memory.add_long_term_memory(
            "episodic", [self.triples[4]], **episodic_qualifiers_2
        )
        self.memory.memory.add_long_term_memory(
            "episodic", [self.triples[5]], **episodic_qualifiers_3
        )
        self.memory.memory.add_long_term_memory(
            "episodic", [self.triples[6]], **episodic_qualifiers_1
        )
        self.memory.memory.add_long_term_memory(
            "episodic", [self.triples[7]], **episodic_qualifiers_2
        )
        self.memory.memory.add_long_term_memory(
            "episodic", [self.triples[8]], **episodic_qualifiers_3
        )
        self.memory.memory.add_long_term_memory(
            "episodic", [self.triples[9]], **episodic_qualifiers_1
        )
        self.memory.memory.add_long_term_memory(
            "episodic", [self.triples[10]], **episodic_qualifiers_2
        )

        # Add semantic memory
        semantic_qualifiers = {"derivedFrom": "animal_research", "strength": 5}
        self.memory.memory.add_long_term_memory(
            "semantic", [self.triples[7]], **semantic_qualifiers
        )
        self.memory.memory.add_long_term_memory(
            "semantic", [self.triples[7]], **semantic_qualifiers
        )
        self.memory.memory.add_long_term_memory(
            "semantic", [self.triples[10]], **semantic_qualifiers
        )
        self.memory.memory.add_long_term_memory(
            "semantic", [self.triples[10]], **semantic_qualifiers
        )

        # Add a short-term memory (recent event)
        self.memory.memory.add_short_term_memory(
            [self.triples[8]], location="Alice's home"
        )
        self.memory.memory.add_short_term_memory(
            [self.triples[8]], location="Alice's home"
        )

        # Add another short-term memory
        self.memory.memory.add_short_term_memory(
            [self.triples[9]], location="Paris Cafe"
        )
        self.memory.memory.add_short_term_memory(
            [self.triples[9]], location="Paris Cafe"
        )

    def test_working_memory_hop_0(self):
        """Test that hop=0 only retrieves short-term memories involving Alice."""
        trigger_node = URIRef("https://example.org/person/Alice")
        working_memory = self.memory.get_working_memory(
            trigger_node=trigger_node, hops=0
        )

        self.assertEqual(working_memory.get_triple_count(), 2)
        self.assertEqual(working_memory.get_memory_count(), 4)

    def test_working_memory_hop_1(self):
        """Test that hop=1 retrieves immediate neighbors' relationships."""
        trigger_node = URIRef("https://example.org/person/Alice")
        working_memory = self.memory.get_working_memory(
            trigger_node=trigger_node, hops=1
        )

        self.assertEqual(working_memory.get_triple_count(), 5)
        self.assertEqual(working_memory.get_memory_count(), 9)

    def test_working_memory_hop_2(self):
        """Test that hop=2 retrieves 2-hop neighbors' relationships."""
        trigger_node = URIRef("https://example.org/person/Alice")
        working_memory = self.memory.get_working_memory(
            trigger_node=trigger_node, hops=2
        )

        self.assertEqual(working_memory.get_triple_count(), 10)
        self.assertEqual(working_memory.get_memory_count(), 16)

    def test_working_memory_hop_3(self):
        """Test that hop=3 retrieves 3-hop neighbors' relationships."""
        trigger_node = URIRef("https://example.org/person/Alice")
        working_memory = self.memory.get_working_memory(
            trigger_node=trigger_node, hops=3
        )

        self.assertEqual(working_memory.get_triple_count(), 11)
        self.assertEqual(working_memory.get_memory_count(), 19)

    def test_working_memory_include_all_long_term(self):
        """Test that all long-term memories are included when include_all_long_term=True."""
        working_memory = self.memory.get_working_memory(include_all_long_term=True)

        self.assertEqual(working_memory.get_triple_count(), 11)
        self.assertEqual(working_memory.get_memory_count(), 19)

    def test_recalled_value_increment(self):
        """Test that the recalled value increments correctly."""
        trigger_node = URIRef("https://example.org/person/Alice")

        # Retrieve working memory at different hops
        self.memory.get_working_memory(trigger_node=trigger_node, hops=1)
        self.memory.get_working_memory(trigger_node=trigger_node, hops=2)

        # Check that recalled has incremented accordingly
        working_memory = self.memory.get_working_memory(
            trigger_node=trigger_node, hops=3
        )

        # Find an example of a statement and assert its recall count
        memory_statements = working_memory.graph.triples((None, None, None))
        for triple in memory_statements:
            if str(triple[1]) == "met" and str(triple[2]) == "Bob":
                # Ensure the 'recalled' qualifier has increased properly (should be 3)
                qualifiers = list(working_memory.graph.predicate_objects(triple[0]))
                for pred, obj in qualifiers:
                    if str(pred) == "recalled":
                        self.assertEqual(int(obj), 3)

    def test_empty_memory(self):
        """Test that working memory handles empty memory cases."""
        empty_memory_system = MemorySystem()
        working_memory = empty_memory_system.get_working_memory(
            URIRef("https://example.org/person/Alice"), hops=1
        )

        self.assertEqual(working_memory.get_triple_count(), 0)
        self.assertEqual(working_memory.get_memory_count(), 0)

    def test_invalid_trigger_node(self):
        """Test behavior when an invalid trigger node is provided."""
        with self.assertRaises(ValueError):
            self.memory.get_working_memory(trigger_node=None, hops=1)
