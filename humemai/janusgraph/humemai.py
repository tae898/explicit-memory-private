"""Humemai class"""

import os
import logging
import docker
import nest_asyncio
from gremlin_python.process.graph_traversal import __
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.structure.graph import Graph
from gremlin_python.process.graph_traversal import GraphTraversalSource
from gremlin_python.process.traversal import T, Direction
from gremlin_python.driver.serializer import GraphSONSerializersV3d0
from humemai.janusgraph.utils.docker import (
    start_containers,
    stop_containers,
    remove_containers,
    remove_all_data as remove_all_data_util,
)

from humemai.memory import (
    Memory,
    ShortMemory,
    LongMemory,
    EpisodicMemory,
    SemanticMemory,
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("humemai.janusgraph.Humemai")


class Humemai:
    def __init__(
        self,
        cassandra_container_name="cassandra",
        janusgraph_container_name="janusgraph",
        gremlin_server_url="ws://localhost:8182/gremlin",
        gremlin_traversal_source="g",
        cassandra_data_dir="./cassandra_data",
        configs_dir="./configs",
        janusgraph_config="janusgraph.properties",
        gremlin_server_config="gremlin-server.yaml",
    ) -> None:
        """
        Initialize a Humemai object for connecting to JanusGraph and Cassandra
        containers.

        Args:
            cassandra_container_name (str): Name of the Cassandra container.
            janusgraph_container_name (str): Name of the JanusGraph container.
            gremlin_server_url (str): URL for connecting to the Gremlin server.
            gremlin_traversal_source (str): Traversal source name for Gremlin.
            cassandra_data_dir (str): Directory for Cassandra data persistence.
            configs_dir (str): Directory containing JanusGraph and Gremlin Server
            configuration files.
            janusgraph_config (str): JanusGraph configuration file.
            gremlin_server_config (str): Gremlin Server configuration file.
        """

        self.cassandra_container_name = cassandra_container_name
        self.janusgraph_container_name = janusgraph_container_name
        self.gremlin_server_url = gremlin_server_url
        self.gremlin_traversal_source = gremlin_traversal_source
        self.cassandra_data_dir = cassandra_data_dir
        self.configs_dir = configs_dir
        self.janusgraph_config = janusgraph_config
        self.gremlin_server_config = gremlin_server_config

        # Initialize Docker client
        self.client = docker.from_env()

        # Set up Gremlin connection and traversal source (to be initialized in connect method)
        self.connection = None
        self.g = None

        # Logging configuration
        self.logger = logger

        self.memory_id = 0

    def reset_memory_id(self) -> None:
        """Reset the memory ID counter to 0."""
        self.memory_id = 0

    def start_containers(self, warmup_seconds: int = 10) -> None:
        """Start the Cassandra and JanusGraph containers with optional warmup time.

        Args:
            warmup_seconds (int): Number of seconds to wait after starting the
                containers
        """
        start_containers(
            configs_dir=self.configs_dir,
            janusgraph_config=self.janusgraph_config,
            gremlin_server_config=self.gremlin_server_config,
            cassandra_data_dir=self.cassandra_data_dir,
            cassandra_container_name=self.cassandra_container_name,
            janusgraph_container_name=self.janusgraph_container_name,
            warmup_seconds=warmup_seconds,
        )

    def stop_containers(self) -> None:
        """Stop the Cassandra and JanusGraph containers."""
        stop_containers(
            cassandra_container_name=self.cassandra_container_name,
            janusgraph_container_name=self.janusgraph_container_name,
        )

    def remove_containers(self) -> None:
        """Remove the Cassandra and JanusGraph containers."""
        remove_containers(
            cassandra_container_name=self.cassandra_container_name,
            janusgraph_container_name=self.janusgraph_container_name,
        )

    def connect(self) -> None:
        """Establish a connection to the Gremlin server."""
        try:
            if not self.connection:
                # Apply nest_asyncio to allow nested event loops (useful in Jupyter notebooks)
                nest_asyncio.apply()

                # Initialize Gremlin connection using GraphSON 3.0 serializer
                self.connection = DriverRemoteConnection(
                    self.gremlin_server_url,
                    self.gremlin_traversal_source,
                    message_serializer=GraphSONSerializersV3d0(),
                )
                # Set up the traversal source
                self.g = Graph().traversal().withRemote(self.connection)
                self.logger.debug("Successfully connected to the Gremlin server.")
        except Exception as e:
            self.logger.error(f"Failed to connect to the Gremlin server: {e}")
            raise

    def disconnect(self) -> None:
        """Close the connection to the Gremlin server."""
        if self.connection:
            try:
                self.connection.close()
                self.logger.debug("Disconnected from the Gremlin server.")
            except Exception as e:
                self.logger.error(f"Failed to disconnect from the Gremlin server: {e}")
            finally:
                self.connection = None
                self.g = None

    def remove_all(self) -> None:
        """Remove all vertices and edges from the JanusGraph graph."""
        if self.g:
            remove_all_data_util(self.g)
        else:
            self.logger.warning("Graph traversal source (g) is not initialized.")

    def write_memory(self, memory: Memory) -> None:
        """
        Write a new memory to the graph, consisting of two nodes and an edge connecting them.

        Args:
            memory (Memory): An instance of Memory or its subclass.

        """
        try:
            # Assign a unique memory_id if not already set in the object
            if memory.memory_id is None:
                memory.memory_id = self.memory_id

            # Add the head node with label and properties
            node1 = self.g.addV(memory.head_label).property(
                "memory_id", memory.memory_id
            )
            for key, value in memory.head_properties.items():
                node1 = node1.property(key, value)
            node1 = node1.next()

            # Add the tail node with label and properties
            node2 = self.g.addV(memory.tail_label).property(
                "memory_id", memory.memory_id
            )
            for key, value in memory.tail_properties.items():
                node2 = node2.property(key, value)
            node2 = node2.next()

            # Add the edge between head and tail nodes with label and properties
            edge = (
                self.g.V(node1.id)
                .addE(memory.edge_label)
                .to(__.V(node2.id))
                .property("memory_id", memory.memory_id)
            )
            for key, value in memory.edge_properties.items():
                edge = edge.property(key, value)
            edge = edge.next()

            # Log and return the edge ID
            self.logger.debug(
                f"Created memory with edge ID: {edge.id} and memory_id: {memory.memory_id} between nodes {node1.id} and {node2.id}"
            )

            # Increment memory_id for the next memory entry if it was newly assigned
            if memory.memory_id == self.memory_id:
                self.memory_id += 1

        except Exception as e:
            self.logger.error(f"Failed to write memory: {e}")
            raise

    def read_memory(self, memory_id: int) -> Memory:
        """
        Read a memory based on its unique integer memory_id.

        Args:
            memory_id (int): Unique integer identifier for the memory.

        Returns:
            Memory: A Memory instance (or subclass, depending on edge properties) representing the memory.
        """
        try:
            # Retrieve the edge with the specified memory_id
            edge = self.g.E().has("memory_id", memory_id).next()

            # Retrieve edge label and properties
            edge_label = edge.label
            edge_properties = {prop.key: prop.value for prop in edge.properties}

            # Determine subclass based on properties
            memory_class = Memory
            if "current_time" in edge_properties:
                memory_class = ShortMemory
            elif "num_recalled" in edge_properties:
                if "event_time" in edge_properties:
                    memory_class = EpisodicMemory
                elif (
                    "known_since" in edge_properties
                    and "derived_from" in edge_properties
                ):
                    memory_class = SemanticMemory
                else:
                    memory_class = LongMemory

            # Retrieve connected nodes (head and tail) with labels and properties
            tail_id = edge.inV.id
            tail_label = edge.inV.label
            tail_properties = {
                key: val[0]
                for key, val in self.g.V(edge.inV.id).valueMap().next().items()
            }

            head_id = edge.outV.id
            head_label = edge.outV.label
            head_properties = {
                key: val[0]
                for key, val in self.g.V(edge.outV.id).valueMap().next().items()
            }

            # Construct and return the appropriate memory object
            memory = memory_class(
                head_label=head_label,
                tail_label=tail_label,
                edge_label=edge_label,
                memory_id=memory_id,
                head_properties=head_properties,
                tail_properties=tail_properties,
                edge_properties=edge_properties,
            )

            self.logger.debug(f"Retrieved memory for memory_id {memory_id}: {memory}")
            return memory

        except Exception as e:
            self.logger.error(f"Failed to read memory: {e}")
            raise

    def delete_memory(self, memory_id: int) -> None:
        """Delete a memory based on memory ID.

        Args:
            memory_id (int): Unique integer identifier for the memory.
        """
        self.g.E().has("memory_id", memory_id).drop().iterate()
        self.g.V().has("memory_id", memory_id).drop().iterate()

    def read_all(self) -> dict:
        """
        read all nodes (vertices) and edges in the database, including all properties.

        Returns:
            dict: A dictionary containing lists of all vertices and edges with their properties.
        """
        try:
            # read all vertices and their properties
            vertices = self.g.V().elementMap().toList()

            # read all edges and their properties
            edges = self.g.E().elementMap().toList()

            # Log and return the results
            self.logger.debug(
                f"readd {len(vertices)} vertices and {len(edges)} edges from the database."
            )
            return {"vertices": vertices, "edges": edges}

        except Exception as e:
            self.logger.error(f"Failed to read all data: {e}")
            raise

    def get_all_short_term_memories(self) -> list:
        """
        Retrieve all short-term memories from the database, identified by the presence
        of the 'current_time' property in the edge.

        Returns:
            list: A list of ShortMemory objects.
        """
        short_memories = []

        try:
            # Find all edges that have the 'current_time' property, indicating short-term memories
            edges = self.g.E().has("current_time").toList()

            for edge in edges:
                # Retrieve edge details
                edge_label = edge.label
                edge_properties = {prop.key: prop.value for prop in edge.properties}

                # Retrieve connected vertices (head and tail) with labels and properties
                tail_id = edge.inV.id
                tail_label = edge.inV.label
                tail_properties = {
                    key: val[0]
                    for key, val in self.g.V(edge.inV.id).valueMap().next().items()
                }

                head_id = edge.outV.id
                head_label = edge.outV.label
                head_properties = {
                    key: val[0]
                    for key, val in self.g.V(edge.outV.id).valueMap().next().items()
                }

                # Create a ShortMemory object
                memory = ShortMemory(
                    head_label=head_label,
                    tail_label=tail_label,
                    edge_label=edge_label,
                    memory_id=edge_properties.get("memory_id"),
                    head_properties=head_properties,
                    tail_properties=tail_properties,
                    edge_properties=edge_properties,
                )

                # Add to the list
                short_memories.append(memory)

            self.logger.debug(f"Retrieved {len(short_memories)} short-term memories.")
            return short_memories

        except Exception as e:
            self.logger.error(f"Failed to retrieve short-term memories: {e}")
            raise

    def count_short_term_memories(self) -> int:
        """
        Count the number of short-term memories in the database.

        Returns:
            int: The number of short-term memories.
        """
        try:
            # Count the number of edges with 'current_time' property
            count = self.g.E().has("current_time").count().next()
            self.logger.debug(f"Found {count} short-term memories.")
            return count

        except Exception as e:
            self.logger.error(f"Failed to count short-term memories: {e}")
            raise

    def get_all_episodic_memories(self) -> list:
        """
        Retrieve all episodic memories from the database, identified by the presence
        of the 'event_time' property in the edge.

        Returns:
            list: A list of EpisodicMemory objects.
        """
        episodic_memories = []

        try:
            # Find all edges that have the 'event_time' property, indicating episodic memories
            edges = self.g.E().has("event_time").toList()

            for edge in edges:
                # Retrieve edge details
                edge_label = edge.label
                edge_properties = {prop.key: prop.value for prop in edge.properties}

                # Retrieve connected vertices (head and tail) with labels and properties
                tail_id = edge.inV.id
                tail_label = edge.inV.label
                tail_properties = {
                    key: val[0]
                    for key, val in self.g.V(edge.inV.id).valueMap().next().items()
                }

                head_id = edge.outV.id
                head_label = edge.outV.label
                head_properties = {
                    key: val[0]
                    for key, val in self.g.V(edge.outV.id).valueMap().next().items()
                }

                # Create an EpisodicMemory object
                memory = EpisodicMemory(
                    head_label=head_label,
                    tail_label=tail_label,
                    edge_label=edge_label,
                    memory_id=edge_properties.get("memory_id"),
                    head_properties=head_properties,
                    tail_properties=tail_properties,
                    edge_properties=edge_properties,
                )

                # Add to the list
                episodic_memories.append(memory)

            self.logger.debug(f"Retrieved {len(episodic_memories)} episodic memories.")
            return episodic_memories

        except Exception as e:
            self.logger.error(f"Failed to retrieve episodic memories: {e}")
            raise

    def count_episodic_memories(self) -> int:
        """
        Count the number of episodic memories in the database.

        Returns:
            int: The number of episodic memories.
        """
        try:
            # Count the number of edges with 'event_time' property
            count = self.g.E().has("event_time").count().next()
            self.logger.debug(f"Found {count} episodic memories.")
            return count

        except Exception as e:
            self.logger.error(f"Failed to count episodic memories: {e}")
            raise

    def get_all_semantic_memories(self) -> list:
        """
        Retrieve all semantic memories from the database, identified by the presence
        of the 'known_since' property in the edge.

        Returns:
            list: A list of SemanticMemory objects.
        """
        semantic_memories = []

        try:
            # Find all edges that have the 'known_since' property, indicating semantic memories
            edges = self.g.E().has("known_since").toList()

            for edge in edges:
                # Retrieve edge details
                edge_label = edge.label
                edge_properties = {prop.key: prop.value for prop in edge.properties}

                # Retrieve connected vertices (head and tail) with labels and properties
                tail_id = edge.inV.id
                tail_label = edge.inV.label
                tail_properties = {
                    key: val[0]
                    for key, val in self.g.V(edge.inV.id).valueMap().next().items()
                }

                head_id = edge.outV.id
                head_label = edge.outV.label
                head_properties = {
                    key: val[0]
                    for key, val in self.g.V(edge.outV.id).valueMap().next().items()
                }

                # Create a SemanticMemory object
                memory = SemanticMemory(
                    head_label=head_label,
                    tail_label=tail_label,
                    edge_label=edge_label,
                    memory_id=edge_properties.get("memory_id"),
                    head_properties=head_properties,
                    tail_properties=tail_properties,
                    edge_properties=edge_properties,
                )

                # Add to the list
                semantic_memories.append(memory)

            self.logger.debug(f"Retrieved {len(semantic_memories)} semantic memories.")
            return semantic_memories

        except Exception as e:
            self.logger.error(f"Failed to retrieve semantic memories: {e}")
            raise

    def count_semantic_memories(self) -> int:
        """
        Count the number of semantic memories in the database.

        Returns:
            int: The number of semantic memories.
        """
        try:
            # Count the number of edges with 'known_since' property
            count = self.g.E().has("known_since").count().next()
            self.logger.debug(f"Found {count} semantic memories.")
            return count

        except Exception as e:
            self.logger.error(f"Failed to count semantic memories: {e}")
            raise

    def get_all_long_term_memories(self) -> list:
        """
        Retrieve all long-term memories from the database, identified by the presence
        of the 'num_recalled' property in the edge, excluding those with 'current_time'.

        Returns:
            list: A list of LongMemory objects, which may include EpisodicMemory and
                SemanticMemory instances.
        """
        long_term_memories = []

        try:
            # Find all edges that have 'num_recalled' property and do not have 'current_time'
            edges = self.g.E().has("num_recalled").not_(__.has("current_time")).toList()

            for edge in edges:
                # Retrieve edge details
                edge_label = edge.label
                edge_properties = {prop.key: prop.value for prop in edge.properties}

                # Determine the specific subclass
                if "event_time" in edge_properties:
                    memory_class = EpisodicMemory
                elif "known_since" in edge_properties:
                    memory_class = SemanticMemory
                else:
                    memory_class = LongMemory

                # Retrieve connected vertices (head and tail) with labels and properties
                tail_id = edge.inV.id
                tail_label = edge.inV.label
                tail_properties = {
                    key: val[0]
                    for key, val in self.g.V(edge.inV.id).valueMap().next().items()
                }

                head_id = edge.outV.id
                head_label = edge.outV.label
                head_properties = {
                    key: val[0]
                    for key, val in self.g.V(edge.outV.id).valueMap().next().items()
                }

                # Create a memory object of the appropriate class
                memory = memory_class(
                    head_label=head_label,
                    tail_label=tail_label,
                    edge_label=edge_label,
                    memory_id=edge_properties.get("memory_id"),
                    head_properties=head_properties,
                    tail_properties=tail_properties,
                    edge_properties=edge_properties,
                )

                # Add to the list
                long_term_memories.append(memory)

            self.logger.debug(
                f"Retrieved {len(long_term_memories)} long-term memories."
            )
            return long_term_memories

        except Exception as e:
            self.logger.error(f"Failed to retrieve long-term memories: {e}")
            raise

    def count_long_term_memories(self) -> int:
        """
        Count the number of long-term memories in the database.

        Returns:
            int: The number of long-term memories.
        """
        try:
            # Count the number of edges with 'num_recalled' property and not 'current_time'
            count = (
                self.g.E()
                .has("num_recalled")
                .not_(__.has("current_time"))
                .count()
                .next()
            )
            self.logger.debug(f"Found {count} long-term memories.")
            return count

        except Exception as e:
            self.logger.error(f"Failed to count long-term memories: {e}")
            raise

    def get_all_memories(self) -> list:
        """
        Retrieve all memories from the database, identified by the presence of 'memory_id'
        property on edges. This includes generic Memory objects as well as specific types
        like ShortMemory, LongMemory, EpisodicMemory, and SemanticMemory.

        Returns:
            list: A combined list of all Memory objects.
        """
        all_memories = []

        try:
            # Find all edges with a 'memory_id' property
            edges = self.g.E().has("memory_id").toList()

            for edge in edges:
                # Convert edge properties to a dictionary
                edge_properties = {prop.key: prop.value for prop in edge.properties}
                edge_label = edge.label
                memory_id = edge_properties.get("memory_id")

                # Determine the specific Memory subclass based on edge properties
                if "current_time" in edge_properties:
                    memory_class = ShortMemory
                elif "num_recalled" in edge_properties:
                    if "event_time" in edge_properties:
                        memory_class = EpisodicMemory
                    elif (
                        "known_since" in edge_properties
                        and "derived_from" in edge_properties
                    ):
                        memory_class = SemanticMemory
                    else:
                        memory_class = LongMemory
                else:
                    memory_class = Memory

                # Retrieve connected vertices (head and tail) with labels and properties
                tail_id = edge.inV.id
                tail_label = edge.inV.label
                tail_properties = {
                    key: val[0]
                    for key, val in self.g.V(tail_id).valueMap().next().items()
                }

                head_id = edge.outV.id
                head_label = edge.outV.label
                head_properties = {
                    key: val[0]
                    for key, val in self.g.V(head_id).valueMap().next().items()
                }

                # Create a memory object of the appropriate class
                memory = memory_class(
                    head_label=head_label,
                    tail_label=tail_label,
                    edge_label=edge_label,
                    memory_id=memory_id,
                    head_properties=head_properties,
                    tail_properties=tail_properties,
                    edge_properties=edge_properties,
                )

                # Add the memory to the list of all memories
                all_memories.append(memory)

            self.logger.debug(f"Retrieved {len(all_memories)} total memories.")
            return all_memories

        except Exception as e:
            self.logger.error(f"Failed to retrieve all memories: {e}")
            raise

    def count_all_memories(self) -> int:
        """
        Count the total number of memories in the database, identified by the presence of
        the 'memory_id' property on edges.

        Returns:
            int: The total count of memories.
        """
        try:
            # Count edges that have the 'memory_id' property
            total_count = self.g.E().has("memory_id").count().next()
            self.logger.debug(f"Total memory count: {total_count}")
            return total_count

        except Exception as e:
            self.logger.error(f"Failed to count all memories: {e}")
            raise

    def _increment_num_recalled(self, memory: Memory) -> None:
        """Helper function to increment num_recalled on vertices and edges of a
        memory.

        Args:
            memory (Memory): A Memory object to be updated.

        """
        # Get the edge with the given memory_id
        edge = self.g.E().has("memory_id", memory.memory_id).next()
        # Convert edge properties to a dictionary
        edge_properties = {prop.key: prop.value for prop in edge.properties}
        # Get the current 'num_recalled' value
        current_num_recalled = edge_properties.get("num_recalled", 0)
        new_num_recalled = current_num_recalled + 1

        edge_id = edge.id["@value"]["relationId"]

        head_id = edge.outV.id
        head_label = edge.outV.label
        head_properties = {
            key: val[0] for key, val in self.g.V(edge.outV.id).valueMap().next().items()
        }

        tail_id = edge.inV.id
        tail_label = edge.inV.label
        tail_properties = {
            key: val[0] for key, val in self.g.V(edge.inV.id).valueMap().next().items()
        }

        self.g.V(head_id).property("num_recalled", new_num_recalled).iterate()
        self.g.V(tail_id).property("num_recalled", new_num_recalled).iterate()
        self.g.E(edge_id).property("num_recalled", new_num_recalled).iterate()

        memory.head_properties["num_recalled"] = new_num_recalled
        memory.tail_properties["num_recalled"] = new_num_recalled
        memory.edge_properties["num_recalled"] = new_num_recalled

    def get_working_memory(
        self,
        include_all_long_term: bool = True,
        trigger_node: str = None,
        hops: int = 1,
    ) -> list:
        """
        Retrieves the working memory, consisting of all short-term memories and partial long-term memories.

        Args:
            include_all_long_term (bool): If True, include all long-term memories.
            trigger_node (str): The starting node ID for traversing the graph.
            hops (int): Number of hops to traverse from the trigger node.

        Returns:
            list: A list of Memory objects representing the working memory.
        """
        if include_all_long_term:
            assert (
                trigger_node is None
            ), "trigger_node must be None when include_all_long_term is True"
        working_memories = []

        # Step 1: Get all short-term memories
        short_term_memories = self.get_all_short_term_memories()
        working_memories.extend(short_term_memories)

        # Step 2: Get all long-term memories within the specified hops
        if include_all_long_term:

            long_term_memories = self.get_all_long_term_memories()
            for memory in long_term_memories:
                self._increment_num_recalled(memory)
                # Add the memory to working_memories
                working_memories.append(memory)

        # Step 2: Get long-term memories within the specified hops
        else:
            if trigger_node is None:
                self.logger.error(
                    "trigger_node must be provided when include_all_long_term is False"
                )
                raise ValueError(
                    "trigger_node must be provided when include_all_long_term is False"
                )

            try:
                # Perform traversal from the trigger node up to 'hops', including both
                # incoming and outgoing edges
                edges_within_hops = (
                    self.g.V()
                    .hasLabel(trigger_node)
                    .repeat(__.bothE().as_("e").bothV().simplePath())
                    .emit()
                    .times(hops)
                    .select("e")
                    .dedup()
                    .has("memory_id")  # Filter to include only edges with a memory_id
                    .not_(__.has("current_time"))  # Exclude short-term memories
                    .toList()
                )

                for edge in edges_within_hops:
                    # Convert edge properties to a dictionary
                    edge_properties = {prop.key: prop.value for prop in edge.properties}
                    edge_label = edge.label
                    memory_id = edge_properties.get("memory_id")

                    # Retrieve connected vertices (head and tail) with labels and properties
                    tail_id = edge.inV.id
                    tail_label = edge.inV.label
                    tail_properties = {
                        key: val[0]
                        for key, val in self.g.V(tail_id).valueMap().next().items()
                    }

                    head_id = edge.outV.id
                    head_label = edge.outV.label
                    head_properties = {
                        key: val[0]
                        for key, val in self.g.V(head_id).valueMap().next().items()
                    }

                    # Determine the specific subclass of Memory
                    if "event_time" in edge_properties:
                        memory_class = EpisodicMemory
                    elif (
                        "known_since" in edge_properties
                        and "derived_from" in edge_properties
                    ):
                        memory_class = SemanticMemory
                    else:
                        memory_class = LongMemory

                    # Create a memory object of the appropriate class
                    memory = memory_class(
                        head_label=head_label,
                        tail_label=tail_label,
                        edge_label=edge_label,
                        memory_id=memory_id,
                        head_properties=head_properties,
                        tail_properties=tail_properties,
                        edge_properties=edge_properties,
                    )

                    # Increment the num_recalled property for vertices and edges using
                    # the helper
                    self._increment_num_recalled(memory)

                    # Add the memory to working_memories
                    working_memories.append(memory)

                self.logger.debug(
                    f"Retrieved {len(working_memories) - len(short_term_memories)} long-term memories within {hops} hops from node '{trigger_node}'."
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to retrieve long-term memories within {hops} hops from node '{trigger_node}': {e}"
                )
                raise

        return working_memories
