1. Working memory is defined as all short-term memories + partial long-term memory

   1. This method takes three arguments: `trigger_node`, `hops` and,
      `include_all_long_term`. If `include_all_long_term` is true then `trigger_node` and
      `hops` are not necessary, since we'll just return all the long-term memories
      along with the short ones. If `include_all_long_term` is False, then we have to
      consider both both `trigger_node` and `hops`, two of which determins the long-term
      memories that we want to fetch. We are gonna fetch all the memories that are within
      `hop`s from the `trigger_node`. There are several things to remember. We are not just
      fetching the nodes, but fetching the memories! Remember the definition of the memory
      we mentioned above. Also, we are considering both outgoing and incoming edges from the
      nodes in consideration.

1. When we recall a long-term memory from the database, we have to increment it in the database.

   1. This should be done with working-memory

1. Implement "event" clustering.

   1. We can do something like Leiden algorithm to find communities to assign an event.

1. visualization
