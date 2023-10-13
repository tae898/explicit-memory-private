import unittest

import numpy as np

from explicit_memory.nn import LSTM


class LSTMTest(unittest.TestCase):
    def test_all(self) -> None:
        configs = []

        for hidden_size in [16, 32]:
            for num_layers in [1, 2]:
                for num_actions in [2, 3]:
                    for embedding_dim in [4, 8]:
                        for capacity in [4, 8]:
                            for include_human in [None, "sum", "concat"]:
                                for batch_first in [True, False]:
                                    for human_embedding_on_object_location in [
                                        True,
                                        False,
                                    ]:
                                        for dueling_dqn in [True, False]:
                                            configs.append(
                                                {
                                                    "hidden_size": hidden_size,
                                                    "num_layers": num_layers,
                                                    "n_actions": num_actions,
                                                    "embedding_dim": embedding_dim,
                                                    "capacity": {
                                                        "episodic": capacity // 2,
                                                        "semantic": capacity // 2,
                                                        "short": capacity // 2,
                                                    },
                                                    "memory_of_interest": [
                                                        "episodic",
                                                        "semantic",
                                                        "short",
                                                    ],
                                                    "entities": [
                                                        "Foo",
                                                        "Bar",
                                                        "laptop",
                                                        "phone",
                                                        "desk",
                                                        "lap",
                                                    ],
                                                    "relations": [],
                                                    "v1_params": {
                                                        "include_human": include_human,
                                                        "human_embedding_on_object_location": human_embedding_on_object_location,
                                                    },
                                                    "v2_params": None,
                                                    "batch_first": batch_first,
                                                    "device": "cpu",
                                                    "dueling_dqn": dueling_dqn,
                                                }
                                            )
        for config in configs:
            lstm = LSTM(**config)

    def test_forward(self) -> None:
        config = {
            "hidden_size": 64,
            "num_layers": 2,
            "n_actions": 3,
            "embedding_dim": 32,
            "capacity": {
                "episodic": 16,
                "semantic": 16,
                "short": 1,
            },
            "memory_of_interest": [
                "episodic",
                "semantic",
                "short",
            ],
            "entities": [
                "Foo",
                "Bar",
                "laptop",
                "phone",
                "desk",
                "lap",
            ],
            "relations": [],
            "v1_params": {
                "include_human": "sum",
                "human_embedding_on_object_location": False,
            },
            "v2_params": None,
            "batch_first": True,
            "device": "cpu",
            "dueling_dqn": True,
        }
        lstm = LSTM(**config)
        lstm.forward(
            np.array(
                [
                    {
                        "episodic": [["Foo's laptop", "atlocation", "desk", 0]],
                        "semantic": [["laptop", "atlocation", "desk", 1]],
                        "short": [["Bar's phone", "atlocation", "lap", 1]],
                    }
                ]
            )
        )
