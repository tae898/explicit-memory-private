import datetime
import os
import random
import shutil
from copy import deepcopy
from typing import Dict, List, Tuple

import gymnasium as gym
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
import torch.optim as optim
from IPython.display import clear_output
from tqdm.auto import tqdm, trange

from explicit_memory.memory import (
    EpisodicMemory,
    MemorySystems,
    SemanticMemory,
    ShortMemory,
)
from explicit_memory.nn import LSTM
from explicit_memory.policy import answer_question, encode_observation, manage_memory
from explicit_memory.utils import (
    ReplayBuffer,
    is_running_notebook,
    write_yaml,
)

from .handcrafted import HandcraftedAgent


class DQNAgent(HandcraftedAgent):
    """DQN Agent interacting with environment.

    Based on https://github.com/Curt-Park/rainbow-is-all-you-need/
    """

    def __init__(
        self,
        env_str: str = "room_env:RoomEnv-v1",
        num_iterations: int = 1280,
        replay_buffer_size: int = 1024,
        warm_start: int = 1024,
        batch_size: int = 1024,
        target_update_rate: int = 10,
        epsilon_decay_until: float = 128 * 16,
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
            "embedding_dim": 32,
            "v1_params": {
                "include_human": "sum",
                "human_embedding_on_object_location": False,
            },
            "v2_params": None,
        },
        run_validation: bool = True,
        run_test: bool = True,
        num_samples_for_results: int = 10,
        plotting_interval: int = 10,
        train_seed: int = 42,
        test_seed: int = 42,
        device: str = "cpu",
        ddqn: bool = False,
        dueling_dqn: bool = False,
    ):
        """Initialization.

        Args
        ----
        env_str: This has to be "room_env:RoomEnv-v1"
        num_iterations: The number of iterations to train the agent.
        replay_buffer_size: The size of the replay buffer.
        warm_start: The number of samples to fill the replay buffer with, before
            starting
        batch_size: The batch size for training This is the amount of samples sampled
            from the replay buffer.
        target_update_rate: The rate to update the target network.
        epsilon_decay_until: The iteration index until which to decay epsilon.
        max_epsilon: The maximum epsilon.
        min_epsilon: The minimum epsilon.
        gamma: The discount factor.
        capacity: The capacity of each human-like memory systems.
        pretrain_semantic: Whether or not to pretrain the semantic memory system.
        nn_params: The parameters for the DQN (function approximator).
        run_validation: Whether or not to run validation.
        run_test: Whether or not to run test.
        num_samples_for_results: The number of samples to validate / test the agent.
        plotting_interval: The interval to plot the results.
        train_seed: The random seed for train.
        test_seed: The random seed for test.
        device: The device to run the agent on. This is either "cpu" or "cuda".

        """
        all_params = deepcopy(locals())
        del all_params["self"]
        del all_params["__class__"]
        self.all_params = deepcopy(all_params)
        super().__init__(
            env_str=env_str,
            policy="rl",
            num_samples_for_results=num_samples_for_results,
            seed=train_seed,
            capacity=capacity,
            pretrain_semantic=pretrain_semantic,
        )
        write_yaml(self.all_params, os.path.join(self.default_root_dir, "train.yaml"))

        self.train_seed = train_seed
        self.test_seed = test_seed

        self.val_filenames = []
        self.is_notebook = is_running_notebook()
        self.num_iterations = num_iterations
        self.plotting_interval = plotting_interval
        self.run_validation = run_validation
        self.run_test = run_test
        self.device = torch.device(device)
        print(f"Running on {self.device}")

        self.replay_buffer_size = replay_buffer_size
        self.batch_size = batch_size
        self.epsilon = max_epsilon
        self.max_epsilon = max_epsilon
        self.min_epsilon = min_epsilon
        self.epsilon_decay_until = epsilon_decay_until
        self.target_update_rate = target_update_rate
        self.gamma = gamma
        self.warm_start = warm_start
        assert self.batch_size <= self.warm_start <= self.replay_buffer_size

        self.action2str = {
            0: "episodic",
            1: "semantic",
            2: "forget",
        }
        self.action_space = gym.spaces.Discrete(len(self.action2str))

        self.ddqn = ddqn
        self.dueling_dqn = dueling_dqn

        self.nn_params = nn_params
        self.nn_params["capacity"] = self.capacity
        self.nn_params["device"] = self.device
        self.nn_params["entities"] = (
            self.env.des.humans + self.env.des.objects + self.env.des.object_locations
        )
        # there is only one relation in v1, so just ignore it.
        self.nn_params["relations"] = []

        self.nn_params["memory_of_interest"] = ["episodic", "semantic", "short"]
        self.nn_params["n_actions"] = len(self.action2str)
        self.nn_params["dueling_dqn"] = self.dueling_dqn

        # networks: dqn, dqn_target
        self.dqn = LSTM(**self.nn_params)
        self.dqn_target = LSTM(**self.nn_params)
        self.dqn_target.load_state_dict(self.dqn.state_dict())
        self.dqn_target.eval()

        self.replay_buffer = ReplayBuffer(
            observation_type="dict", size=replay_buffer_size, batch_size=batch_size
        )

        # optimizer
        self.optimizer = optim.Adam(self.dqn.parameters())

    def select_action(self, state: dict, greedy: bool) -> int:
        """Select an action from the input state.

        Args
        ----
        state: The current state of the memory systems. This is NOT what the gym env
        gives you. This is made by the agent.
        greedy: always pick greedy action if True

        """
        # epsilon greedy policy
        if self.epsilon < np.random.random() or greedy:
            selected_action = self.dqn(np.array([state])).argmax()
            selected_action = selected_action.detach().cpu().numpy().item()

        else:
            selected_action = self.action_space.sample()

        return selected_action

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
        actions. The filling continues until it reaches the warm start size."""

        self.dqn.eval()

        while len(self.replay_buffer) < self.warm_start:
            self.init_memory_systems()
            (observation, question), info = self.env.reset()
            encode_observation(self.memory_systems, observation)

            done = False
            while not done and len(self.replay_buffer) < self.warm_start:
                state = self.memory_systems.return_as_a_dict_list()
                action = self.select_action(state, greedy=False)
                manage_memory(
                    self.memory_systems, self.action2str[action], split_possessive=True
                )

                answer = str(
                    answer_question(self.memory_systems, "episodic_semantic", question)
                )

                (
                    (observation, question),
                    reward,
                    done,
                    truncated,
                    info,
                ) = self.env.step(answer)

                encode_observation(self.memory_systems, observation)
                done = done or truncated
                next_state = self.memory_systems.return_as_a_dict_list()

                transition = [state, action, reward, next_state, done]
                self.replay_buffer.store(*transition)

        self.dqn.train()

    def train(self):
        """Train the agent."""
        self.fill_replay_buffer()  # fill up the buffer till warm start size
        self.num_validation = 0

        self.epsilons = []
        self.training_loss = []
        self.scores = {"train": [], "validation": [], "test": None}

        self.init_memory_systems()
        (observation, question), info = self.env.reset()
        encode_observation(self.memory_systems, observation)

        score = 0
        bar = trange(1, self.num_iterations + 1)
        for self.iteration_idx in bar:
            state = self.memory_systems.return_as_a_dict_list()
            action = self.select_action(state, greedy=False)

            manage_memory(
                self.memory_systems, self.action2str[action], split_possessive=True
            )

            answer = str(
                answer_question(self.memory_systems, "episodic_semantic", question)
            )

            (
                (observation, question),
                reward,
                done,
                truncated,
                info,
            ) = self.env.step(answer)
            score += reward

            encode_observation(self.memory_systems, observation)
            done = done or truncated
            next_state = self.memory_systems.return_as_a_dict_list()

            transition = [state, action, reward, next_state, done]
            self.replay_buffer.store(*transition)

            # if episode ends
            if done:
                self.scores["train"].append(score)
                score = 0
                if self.run_validation:
                    with torch.no_grad():
                        self.validate()

                self.init_memory_systems()
                (observation, question), info = self.env.reset()
                encode_observation(self.memory_systems, observation)

            loss = self.update_model()
            self.training_loss.append(loss)

            # linearly decrease epsilon
            self.epsilon = max(
                self.min_epsilon,
                self.epsilon
                - (self.max_epsilon - self.min_epsilon) / self.epsilon_decay_until,
            )
            self.epsilons.append(self.epsilon)

            # if hard update is needed
            if self.iteration_idx % self.target_update_rate == 0:
                self._target_hard_update()

            # plotting & show training results
            if (
                self.iteration_idx == self.num_iterations
                or self.iteration_idx % self.plotting_interval == 0
            ):
                self._plot()
        with torch.no_grad():
            self.test()

        self.env.close()

    def validate(self) -> None:
        """Validate the agent."""
        self.dqn.eval()

        scores = []
        for _ in range(self.num_samples_for_results):
            self.init_memory_systems()
            (observation, question), info = self.env.reset()
            encode_observation(self.memory_systems, observation)

            done = False
            score = 0
            while not done:
                state = self.memory_systems.return_as_a_dict_list()
                action = self.select_action(state, greedy=True)
                manage_memory(
                    self.memory_systems, self.action2str[action], split_possessive=True
                )

                answer = str(
                    answer_question(self.memory_systems, "episodic_semantic", question)
                )
                (
                    (observation, question),
                    reward,
                    done,
                    truncated,
                    info,
                ) = self.env.step(answer)
                score += reward

                encode_observation(self.memory_systems, observation)
                done = done or truncated

            scores.append(score)

        self.save_validation(scores)
        self.env.close()
        self.num_validation += 1
        self.dqn.train()

    def save_validation(self, scores) -> None:
        """Keep the best validation model.

        Args
        ----
        scores: The scores of one validation episode
        """
        mean_score = round(np.mean(scores).item())
        filename = (
            f"{self.default_root_dir}/"
            f"episode={self.num_validation}_val-score={mean_score}.pt"
        )
        self.val_filenames.append(filename)
        torch.save(self.dqn.state_dict(), filename)
        self.scores["validation"].append(scores)

        scores = []
        for filename in self.val_filenames:
            scores.append(int(filename.split("val-score=")[-1].split(".pt")[0]))

        file_to_keep = self.val_filenames[scores.index(max(scores))]

        for filename in deepcopy(self.val_filenames):
            if filename != file_to_keep:
                os.remove(filename)
                self.val_filenames.remove(filename)

    def test(self, checkpoint: str = None) -> None:
        """Test the agent.

        Args
        ----
        checkpoint: The checkpoint to load the model from. If None, the model from the
            best validation is used.

        """
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
            (observation, question), info = self.env.reset()
            encode_observation(self.memory_systems, observation)

            done = False
            score = 0
            while not done:
                state = self.memory_systems.return_as_a_dict_list()
                action = self.select_action(state, greedy=True)
                manage_memory(
                    self.memory_systems, self.action2str[action], split_possessive=True
                )

                answer = str(
                    answer_question(self.memory_systems, "episodic_semantic", question)
                )
                (
                    (observation, question),
                    reward,
                    done,
                    truncated,
                    info,
                ) = self.env.step(answer)
                score += reward

                encode_observation(self.memory_systems, observation)
                done = done or truncated

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
        }
        write_yaml(results, os.path.join(self.default_root_dir, "results.yaml"))
        write_yaml(
            self.memory_systems.return_as_a_dict_list(),
            os.path.join(self.default_root_dir, "last_memory_state.yaml"),
        )

        self._plot()
        self.env.close()
        self.dqn.train()

    def _compute_dqn_loss(self, samples: Dict[str, np.ndarray]) -> torch.Tensor:
        """Return dqn loss.

        Args
        ----
        samples: A dictionary of samples from the replay buffer.
            obs: np.ndarray,
            act: np.ndarray,
            rew: float,
            next_obs: np.ndarray,
            done: bool,
        """
        state = samples["obs"]
        next_state = samples["next_obs"]
        action = torch.LongTensor(samples["acts"].reshape(-1, 1)).to(self.device)
        reward = torch.FloatTensor(samples["rews"].reshape(-1, 1)).to(self.device)
        done = torch.FloatTensor(samples["done"].reshape(-1, 1)).to(self.device)

        # G_t   = r + gamma * v(s_{t+1})  if state != Terminal
        #       = r                       otherwise
        curr_q_value = self.dqn(state).gather(1, action)
        if self.ddqn:
            next_q_value = (
                self.dqn_target(next_state)
                .gather(1, self.dqn(next_state).argmax(dim=1, keepdim=True))
                .detach()
            )
        else:
            next_q_value = (
                self.dqn_target(next_state).max(dim=1, keepdim=True)[0].detach()
            )
        mask = 1 - done
        target = (reward + self.gamma * next_q_value * mask).to(self.device)

        # calculate dqn loss
        loss = F.smooth_l1_loss(curr_q_value, target)

        return loss

    def _target_hard_update(self):
        """Hard update: target <- local."""
        self.dqn_target.load_state_dict(self.dqn.state_dict())

    def _plot(self):
        """Plot the training progresses."""
        if self.is_notebook:
            clear_output(True)
        plt.figure(figsize=(20, 8))

        if self.scores["train"]:
            plt.subplot(234)
            plt.title(
                f"iteration {self.iteration_idx} out of {self.num_iterations}. "
                f"training score: {self.scores['train'][-1]} out of 128"
            )
            plt.plot(self.scores["train"])
            plt.xlabel("episode")

        if self.scores["validation"]:
            plt.subplot(235)
            val_means = [
                round(np.mean(scores).item()) for scores in self.scores["validation"]
            ]
            plt.title(f"validation score: {val_means[-1]} out of 128")
            plt.plot(val_means)
            plt.xlabel("episode")

        if self.scores["test"]:
            plt.subplot(236)
            plt.title(f"test score: {np.mean(self.scores['test'])} out of 128")
            plt.plot(round(np.mean(self.scores["test"]).item(), 2))
            plt.xlabel("episode")

        plt.subplot(231)
        plt.title("training loss")
        plt.plot(self.training_loss)
        plt.xlabel("update counts")

        plt.subplot(232)
        plt.title("epsilons")
        plt.plot(self.epsilons)
        plt.xlabel("update counts")

        plt.subplots_adjust(hspace=0.5)
        plt.savefig(f"{self.default_root_dir}/plot.png")
        if self.is_notebook:
            plt.show()

    def _console(self):
        """Print the training progresses to the console."""
        if self.scores["train"]:
            tqdm.write(
                f"iteration {self.iteration_idx} out of {self.num_iterations}.\n"
                f"episode {self.num_validation} training score: "
                f"{self.scores['train'][-1]} out of 128"
            )

        if self.scores["validation"]:
            val_means = [
                round(np.mean(scores).item()) for scores in self.scores["validation"]
            ]
            tqdm.write(
                f"episode {self.num_validation} validation score: {val_means[-1]} "
                "out of 128"
            )

        if self.scores["test"]:
            tqdm.write(f"test score: {np.mean(self.scores['test'])} out of 128")

        tqdm.write(
            f"training loss: {self.training_loss[-1]}\nepsilons: {self.epsilons[-1]}\n"
        )
