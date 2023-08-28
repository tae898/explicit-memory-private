import os
from typing import Dict, List, Tuple
import random
from copy import deepcopy
import datetime

import yaml
import gymnasium as gym
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
import torch.optim as optim
from IPython.display import clear_output

from explicit_memory.memory import EpisodicMemory, SemanticMemory, ShortMemory
from explicit_memory.policy import (
    answer_question,
    encode_observation,
    manage_memory,
)


from explicit_memory.utils import ReplayBuffer
from nn import LSTM


class HandcraftedAgent:

    """Handcrafted agent interacting with environment. This agent is not trained.
    Only one of the three agents, i.e., random, episodic_only, and semantic_only are
    suported
    """

    def __init__(
        self,
        env_str: str = "room_env:RoomEnv1-v1",
        policy: str = "random",
        num_samples_for_results: int = 10,
        test_seed: int = 42,
        capacity: dict = {
            "episodic": 16,
            "semantic": 16,
            "short": 1,
        },
    ):
        """Initialization.

        Args
        ----
        env_str: This has to be "room_env:RoomEnv1-v1"
        policy: The memory management policy. Choose one of "random", "episodic_only",
                or "semantic_only".
        num_samples_for_results: The number of samples to validate / test the agent.
        test_seed: The random seed for test.
        capacity: The capacity of each human-like memory systems.

        """
        self.all_params = deepcopy(locals())
        del self.all_params["self"]
        self.env_str = env_str
        self.policy = policy
        assert self.policy in ["random", "episodic_only", "semantic_only"]
        self.num_samples_for_results = num_samples_for_results
        self.test_seed = test_seed
        self.capacity = capacity

        self.env = gym.make(self.env_str, seed=self.test_seed)

        self.default_root_dir = f"./training_results/{str(datetime.datetime.now())}"
        os.makedirs(self.default_root_dir, exist_ok=True)

    def init_memory_systems(self, num_actions: int = 3) -> None:
        """Initialize the agent's memory systems."""
        self.action_space = gym.spaces.Discrete(num_actions)
        self.memory_systems = {
            "episodic": EpisodicMemory(capacity=self.capacity["episodic"]),
            "semantic": SemanticMemory(capacity=self.capacity["semantic"]),
            "short": ShortMemory(capacity=self.capacity["short"]),
        }

    def find_answer(self) -> str:
        """Find an answer to the question, by looking up the memory systems."""
        if self.policy.lower() == "random":
            qa_policy = "episodic_semantic"
        elif self.policy.lower() == "episodic_only":
            qa_policy = "episodic"
        elif self.policy.lower() == "semantic_only":
            qa_policy = "semantic"
        else:
            raise ValueError("Unknown policy.")

        answer = answer_question(self.memory_systems, qa_policy, self.question)

        return str(answer).lower()

    def test(self):
        """Test the agent. There is no training for this agent, since it is handcrafted."""
        self.scores = []
        for _ in range(self.num_samples_for_results):
            self.init_memory_systems()
            (observation, self.question), info = self.env.reset()
            encode_observation(self.memory_systems, observation)

            done = False
            score = 0
            while not done:
                if self.policy.lower() == "random":
                    selected_action = random.choice(["episodic", "semantic", "forget"])
                    manage_memory(self.memory_systems, selected_action)
                elif self.policy.lower() == "episodic_only":
                    manage_memory(self.memory_systems, "episodic")
                elif self.policy.lower() == "semantic_only":
                    manage_memory(self.memory_systems, "semantic")
                else:
                    raise ValueError("Unknown policy.")

                answer = self.find_answer()
                (
                    (observation, self.question),
                    reward,
                    done,
                    truncated,
                    info,
                ) = self.env.step(answer)

                encode_observation(self.memory_systems, observation)
                score += reward
            self.scores.append(score)

        results = {
            "test_score": {
                "mean": round(np.mean(self.scores).item(), 2),
                "std": round(np.std(self.scores).item(), 2),
            }
        }
        with open(os.path.join(self.default_root_dir, "results.yaml"), "w") as f:
            yaml.dump(results, f)

        with open(os.path.join(self.default_root_dir, "hparams.yaml"), "w") as f:
            yaml.dump(self.all_params, f)


class DQNAgent:
    """DQN Agent interacting with environment."""

    def __init__(
        self,
        env_str: str,
        num_iterations: int,
        replay_buffer_size: int,
        batch_size: int,
        target_update_rate: int,
        epsilon_decay: float,
        max_epsilon: float = 1.0,
        min_epsilon: float = 0.1,
        gamma: float = 0.65,
        capacity: dict = {
            "episodic": 16,
            "semantic": 16,
            "short": 1,
        },
        pretrain_semantic: bool = False,
        nn_params: dict = {
            "hidden_size": 64,
            "num_layers": 2,
            "n_actions": 3,
            "embedding_dim": 32,
            "include_human": "sum",
        },
        run_validation: bool = True,
        run_test: bool = True,
        num_samples_for_results: int = 10,
        plot_results: bool = True,
        plotting_interval: int = 10,
        train_seed: int = 42,
        test_seed: int = 42,
    ):
        """Initialization.

        Args
        ----
        env_str: This has to be "room_env:RoomEnv1-v1"
        num_iterations: The number of iterations to train the agent.
        replay_buffer_size: The size of the replay buffer.
        batch_size: The batch size for training.
        target_update_rate: The rate to update the target network.
        epsilon_decay: The decay rate of epsilon.
        max_epsilon: The maximum epsilon.
        min_epsilon: The minimum epsilon.
        gamma: The discount factor.
        capacity: The capacity of each human-like memory systems.
        pretrain_semantic: Whether or not to pretrain the semantic memory system.
        nn_params: The parameters for the neural network (function approximator).
        run_validation: Whether or not to run validation.
        run_test: Whether or not to run test.
        num_samples_for_results: The number of samples to validate / test the agent.
        plot_results: Whether or not to plot the results while training. In order to
            make this happen, you have to run this class in a Jupyter notebook.
        plotting_interval: The interval to plot the results.
        train_seed: The random seed for train.
        test_seed: The random seed for test.

        """
        self.all_params = deepcopy(locals())
        del self.all_params["self"]
        self.env_str = env_str
        self.num_iterations = num_iterations
        self.plotting_interval = plotting_interval
        self.train_seed = train_seed
        self.test_seed = test_seed
        self.run_validation = run_validation
        if self.run_validation:
            self.default_root_dir = f"./training_results/{str(datetime.datetime.now())}"
            os.makedirs(self.default_root_dir, exist_ok=True)
            self.val_filenames = []
        self.run_test = run_test
        self.num_samples_for_results = num_samples_for_results
        self.plot_results = plot_results
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(self.device)

        self.env = gym.make(self.env_str, seed=self.train_seed)
        self.capacity = capacity
        self.nn_params = nn_params
        self.nn_params["capacity"] = self.capacity
        self.nn_params["device"] = self.device
        self.nn_params["entities"] = {
            "humans": self.env.des.humans,
            "objects": self.env.des.objects,
            "object_locations": self.env.des.object_locations,
        }
        self.replay_buffer = ReplayBuffer(replay_buffer_size, batch_size)
        self.batch_size = batch_size
        self.epsilon = max_epsilon
        self.epsilon_decay = epsilon_decay
        self.max_epsilon = max_epsilon
        self.min_epsilon = min_epsilon
        self.target_update_rate = target_update_rate
        self.gamma = gamma

        # networks: dqn, dqn_target
        self.dqn = LSTM(**self.nn_params)
        self.dqn_target = LSTM(**self.nn_params)
        self.dqn_target.load_state_dict(self.dqn.state_dict())
        self.dqn_target.eval()

        # optimizer
        self.optimizer = optim.Adam(self.dqn.parameters())

        # transition to store in replay buffer
        self.transition = list()

        # mode: train / test
        self.is_test = False

        self.pretrain_semantic = pretrain_semantic

    def select_action(self, state: dict) -> np.ndarray:
        """Select an action from the input state."""
        # epsilon greedy policy
        if self.epsilon > np.random.random() and not self.is_test:
            selected_action = self.action_space.sample()

        else:
            selected_action = self.dqn(state).argmax()
            selected_action = selected_action.detach().cpu().numpy()

        if not self.is_test:
            self.transition = [state, selected_action]

        return selected_action

    def find_answer(self) -> str:
        """Find an answer to the question."""
        answer = answer_question(
            self.memory_systems, "episodic_semantic", self.question
        )

        return str(answer).lower()

    def get_memory_state(self) -> dict:
        """Return the current state of the memory systems."""
        return {
            "episodic": self.memory_systems["episodic"].return_as_dicts(),
            "semantic": self.memory_systems["semantic"].return_as_dicts(),
            "short": self.memory_systems["short"].return_as_dicts(),
        }

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, np.float64, bool]:
        """Take an action and return the response of the env."""
        if action == 0:
            manage_memory(self.memory_systems, "episodic")
        elif action == 1:
            manage_memory(self.memory_systems, "semantic")
        elif action == 2:
            manage_memory(self.memory_systems, "forget")
        else:
            raise ValueError

        answer = self.find_answer()

        (observation, self.question), reward, done, truncated, info = self.env.step(
            answer
        )
        encode_observation(self.memory_systems, observation)
        done = done or truncated
        next_state = self.get_memory_state()
        if not self.is_test:
            self.transition += [reward, next_state, done]
            self.replay_buffer.store(*self.transition)

        return next_state, reward, done

    def update_model(self) -> torch.Tensor:
        """Update the model by gradient descent."""
        samples = self.replay_buffer.sample_batch()

        loss = self._compute_dqn_loss(samples)

        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        return loss.item()

    def fill_replay_buffer(self) -> None:
        """Make the replay buffer full in the beginning with the uniformly-sampled
        actions."""

        self.is_test = False
        while len(self.replay_buffer) < self.batch_size:
            self.init_memory_systems()
            (observation, self.question), info = self.env.reset()
            encode_observation(self.memory_systems, observation)

            done = False
            while not done:
                state = self.get_memory_state()
                action = self.select_action(state)
                next_state, reward, done = self.step(action)

                state = next_state

        self.dqn.train()

    def train(self):
        """Train the agent."""
        self.fill_replay_buffer()
        self.is_test = False
        self.num_validation = 0

        self.init_memory_systems()
        (observation, self.question), info = self.env.reset()
        encode_observation(self.memory_systems, observation)

        self.epsilons = []
        self.training_loss = []
        self.scores = {"train": [], "validation": [], "test": None}

        score = 0
        for self.iteration_idx in range(1, self.num_iterations + 1):
            state = self.get_memory_state()
            action = self.select_action(state)
            next_state, reward, done = self.step(action)

            state = next_state
            score += reward

            # if episode ends
            if done:
                self.scores["train"].append(score)
                score = 0
                if self.run_validation:
                    self.validate()

                self.init_memory_systems()
                (observation, self.question), info = self.env.reset()
                encode_observation(self.memory_systems, observation)

            loss = self.update_model()
            self.training_loss.append(loss)

            # linearly decrease epsilon
            self.epsilon = max(
                self.min_epsilon,
                self.epsilon
                - (self.max_epsilon - self.min_epsilon) * self.epsilon_decay,
            )
            self.epsilons.append(self.epsilon)

            # if hard update is needed
            if self.iteration_idx % self.target_update_rate == 0:
                self._target_hard_update()

            # plotting
            if (
                self.iteration_idx == self.num_iterations
                or self.iteration_idx % self.plotting_interval == 0
            ) and self.plot_results:
                self._plot()

        self.test()
        self.env.close()

    def choose_best_val(self, filenames: list):
        scores = []
        for filename in filenames:
            scores.append(int(filename.split("val-score=")[-1].split(".pt")[0]))
        return filenames[scores.index(max(scores))]

    def validate(self) -> None:
        """Validate the agent."""
        self.is_test = True
        self.dqn.eval()

        scores = []
        for _ in range(self.num_samples_for_results):
            self.init_memory_systems()
            (observation, self.question), info = self.env.reset()
            encode_observation(self.memory_systems, observation)

            done = False
            score = 0
            while not done:
                state = self.get_memory_state()
                action = self.select_action(state)
                next_state, reward, done = self.step(action)

                state = next_state
                score += reward
            scores.append(score)

        mean_score = round(np.mean(scores).item())
        filename = (
            f"{self.default_root_dir}/"
            f"episode={self.num_validation}_val-score={mean_score}.pt"
        )
        self.val_filenames.append(filename)
        torch.save(self.dqn.state_dict(), filename)
        self.scores["validation"].append(scores)

        file_to_keep = self.choose_best_val(self.val_filenames)

        for filename in self.val_filenames:
            if filename != file_to_keep:
                os.remove(filename)
                self.val_filenames.remove(filename)

        self.env.close()
        self.num_validation += 1
        self.is_test = False
        self.dqn.train()

    def test(self, checkpoint: str = None) -> None:
        """Test the agent."""
        self.is_test = True
        self.env = gym.make(self.env_str, seed=self.test_seed)
        self.dqn.eval()
        if self.run_validation:
            assert len(self.val_filenames) == 1
            self.dqn.load_state_dict(torch.load(self.val_filenames[0]))
            if checkpoint is not None:
                self.dqn.load_state_dict(torch.load(checkpoint))

        scores = []
        for _ in range(self.num_samples_for_results):
            self.init_memory_systems()
            (observation, self.question), info = self.env.reset()
            encode_observation(self.memory_systems, observation)

            done = False
            score = 0
            while not done:
                state = self.get_memory_state()
                action = self.select_action(state)
                next_state, reward, done = self.step(action)

                state = next_state
                score += reward
            scores.append(score)

        self.scores["test"] = scores

        results = {
            "train_score": self.scores["train"],
            "validation_score": [
                {
                    "mean": round(np.mean(scores).item(), 2),
                    "std": round(np.std(scores).item(), 2),
                }
                for scores in self.scores["validation"]
            ],
            "test_score": {
                "mean": round(np.mean(self.scores["test"]).item(), 2),
                "std": round(np.std(self.scores["test"]).item(), 2),
            },
            "training_loss": self.training_loss,
            "epsilons": self.epsilons,
        }
        with open(os.path.join(self.default_root_dir, "results.yaml"), "w") as f:
            yaml.dump(results, f)

        with open(os.path.join(self.default_root_dir, "hparams.yaml"), "w") as f:
            yaml.dump(self.all_params, f)

        self._plot()
        self.env.close()
        self.is_test = False
        self.dqn.train()

    def _compute_dqn_loss(self, samples: Dict[str, np.ndarray]) -> torch.Tensor:
        """Return dqn loss."""
        device = self.device  # for shortening the following lines
        state = samples["obs"]
        next_state = samples["next_obs"]
        action = torch.LongTensor(samples["acts"].reshape(-1, 1)).to(device)
        reward = torch.FloatTensor(samples["rews"].reshape(-1, 1)).to(device)
        done = torch.FloatTensor(samples["done"].reshape(-1, 1)).to(device)

        # G_t   = r + gamma * v(s_{t+1})  if state != Terminal
        #       = r                       otherwise
        curr_q_value = self.dqn(state).gather(1, action)
        next_q_value = self.dqn_target(next_state).max(dim=1, keepdim=True)[0].detach()
        mask = 1 - done
        target = (reward + self.gamma * next_q_value * mask).to(self.device)

        # calculate dqn loss
        loss = F.smooth_l1_loss(curr_q_value, target)

        return loss

    def _target_hard_update(self):
        """Hard update: target <- local."""
        self.dqn_target.load_state_dict(self.dqn.state_dict())

    def _plot(
        self,
    ):
        """Plot the training progresses."""
        clear_output(True)
        plt.figure(figsize=(20, 8))

        if self.scores["train"]:
            plt.subplot(231)
            plt.title(
                f"iteration {self.iteration_idx} out of {self.num_iterations}. "
                f"training score: {self.scores['train'][-1]}"
            )
            plt.plot(self.scores["train"])
            plt.xlabel("episode")

        if self.scores["validation"]:
            plt.subplot(232)
            val_means = [
                round(np.mean(scores).item()) for scores in self.scores["validation"]
            ]
            plt.title(f"validation score: {val_means[-1]}")
            plt.plot(val_means)
            plt.xlabel("episode")

        if self.scores["test"]:
            plt.subplot(233)
            plt.title(f"test score: {np.mean(self.scores['test'])}")
            plt.plot(round(np.mean(self.scores["test"]).item(), 2))
            plt.xlabel("episode")

        plt.subplot(234)
        plt.title("training loss")
        plt.plot(self.training_loss)
        plt.xlabel("update counts")

        plt.subplot(235)
        plt.title("epsilons")
        plt.plot(self.epsilons)
        plt.xlabel("update counts")

        plt.subplots_adjust(hspace=0.5)
        plt.show()

    def init_memory_systems(self, num_actions: int = 3) -> None:
        """Initialize the agent's memory systems."""
        self.action_space = gym.spaces.Discrete(num_actions)
        self.memory_systems = {
            "episodic": EpisodicMemory(capacity=self.capacity["episodic"]),
            "semantic": SemanticMemory(capacity=self.capacity["semantic"]),
            "short": ShortMemory(capacity=self.capacity["short"]),
        }

        if self.pretrain_semantic:
            assert self.capacity["semantic"] > 0
            _ = self.memory_systems["semantic"].pretrain_semantic(
                semantic_knowledge=self.env.des.semantic_knowledge,
                return_remaining_space=False,
                freeze=False,
            )
