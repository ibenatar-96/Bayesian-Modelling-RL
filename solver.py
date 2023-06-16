import os.path
import runtime
# import environment
import copy
from users import Human
from agents import AiAgent
import numpyro
import numpyro.distributions as dist
import jax
import time
import random
from tqdm import tqdm
import os
import json
import matplotlib.pyplot as plt


class Solver:
    """
    Solver, in charge of computing Online planner using Q-Learning
    run() is used for running and testing policy computed.
    """

    def __init__(self, model_parameters, environment):
        self._mapping = {}
        self._model_parameters = model_parameters
        self._environment = environment

    def run(self):
        """
        Running using the policy computed in solve() function.
        AI Agent - Uses computed Q-Learning policy to choose which cell to mark next.
        Human (Opponent) - Move is drawn (uniformly) random from all possible actions (empty cells).
        """
        if os.path.exists("Q_VALUES.txt") and runtime.SPARSE:
            print("Q_VALUES exists, loading..")
            policy = self._load_policy("Q_VALUES.txt")
        else:
            policy = self.solve(self._model_parameters)
        board = self._environment.TicTacToe()
        lost_games = []
        opponent = Human(board)
        ai_agent = AiAgent(board, policy)
        for _ in tqdm(range(runtime.GAMES_TEST), desc='Agent Playing Tic-Tac-Toe..'):
            game_log = []
            board.reset()
            while not board.get_state().is_over():
                opponent.play()
                game_log.append(board.get_state())
                ai_agent.play()
                game_log.append(board.get_state())
            if board.get_state().get_winner() != 'O':
                lost_games.append(game_log)
        print(f"Total Games won: {runtime.GAMES_TEST - len(lost_games)}/{runtime.GAMES_TEST}")
        with open("LOST_GAMES.txt", "a") as lg:
            for lost_game in lost_games:
                print("------ NEW GAME ------", file=lg)
                for move in lost_game:
                    move.print_state(lg)

    def solve(self, model_parameters):
        """
        :param model_parameters: mapping between cell and probability of successfully marking in that cell,
        i.e. {1: 1.0, 2: 1.0, 3: 0.7, 4: 1.0, 5: 0.5, ... , 9: 1.0} Q-Learning algorithm to compute policy.
        Return value - Policy Q, that contains a mapping between (state, action) to expected value in case of taking that
        action from that particular state.
        """
        board = self._environment.TicTacToe()
        Q = {}
        for state in board.get_states().values():
            for action in board.get_possible_moves(state):
                Q[(str(state.BOARD), action)] = 0.0
        alpha = runtime.ALPHA
        epsilon = runtime.EPSILON
        discount_factor = runtime.DISCOUNT_FACTOR
        iterations = runtime.ITERATIONS

        def __choose_action(_state, _available_moves, _mark):
            if random.uniform(0, 1) < epsilon:
                return random.choice(_available_moves)
            else:
                Q_values = [__get_Q_value(_state, _action) for _action in _available_moves]
                if _mark == "O":
                    max_Q = max(Q_values)
                else:
                    max_Q = min(Q_values)
                if Q_values.count(max_Q) > 1:
                    best_moves = [i for i in range(len(_available_moves)) if Q_values[i] == max_Q]
                    i = random.choice(best_moves)
                else:
                    i = Q_values.index(max_Q)
            return _available_moves[i]

        def __get_Q_value(_state, _action):
            if (str(_state.BOARD), _action) not in Q:
                raise Exception(f"State: {_state.BOARD}, Action: {_action} not in Q")
            elif (str(_state.BOARD), _action) in Q and Q[(str(_state.BOARD), _action)] is None:
                Q[(str(_state.BOARD), _action)] = 0.0
            return Q[(str(_state.BOARD), _action)]

        def __update_Q_value(_state, _action, _reward, _next_state, _board):
            next_Q_values = [__get_Q_value(_next_state, next_action) for next_action in
                             _board.get_possible_moves(_next_state)]
            max_next_Q = max(next_Q_values) if next_Q_values else 0.0
            Q[(str(_state.BOARD), _action)] += alpha * (
                    _reward + discount_factor * max_next_Q - Q[(str(_state.BOARD), _action)])

        start_time = time.time()
        won_games = 0
        draw_games = 0
        lost_games = 0
        games_won_over_time = []
        for _ in tqdm(range(iterations), desc='Agent Q-Learning'):
            board.reset()
            i = 0
            if _ % (iterations / 10) == 0:
                games_won_over_time.append(won_games)
                won_games = 0
                draw_games = 0
                lost_games = 0
            while not board.get_state().is_over():
                if i % 2 == 0:
                    mark = 'X'
                    second_mark = 'O'
                else:
                    mark = 'O'
                    second_mark = 'X'
                state = copy.deepcopy(board.get_state())
                available_moves = board.get_possible_moves(state)
                action = __choose_action(state, available_moves, mark)
                next_state, reward = board.mark(action, mark)
                if not next_state.is_over():
                    state_ = copy.deepcopy(next_state)
                    available_moves_ = board.get_possible_moves(state_)
                    action_ = __choose_action(state_, available_moves_, second_mark)
                    next_state_, reward = board.mark(action_, second_mark)
                # if state.BOARD == [['X', 'O', 'X'], ['X', 'O', None], [None, None, None]]:
                #     print(f"Next state: {next_state.BOARD}, reward: {reward}, mark: {mark}")
                __update_Q_value(state, action, reward, next_state, board)
                board.update_state(next_state)
                i += 1
                if board.get_state().is_over():
                    if board.get_state().get_winner() == "O":
                        won_games += 1
                    elif board.get_state().get_winner() == "X":
                        lost_games += 1
                    else:
                        draw_games += 1
        with open("GAMES_WON_RATIO.txt", "w") as gw:
            for games_won in games_won_over_time:
                gw.write(f"{str(games_won)}\n")
        end_time = time.time()
        print(f"Total Time: {end_time - start_time}")
        # self._plot_win_ratio(games_won_over_time)
        self._save_policy(Q, "Q_VALUES.txt")
        return Q

    def get_policy(self):
        return self._mapping

    @staticmethod
    def _save_policy(Q, txt_file):
        jsonifable = {f"{str(state)}:{str(action)}": val for (state, action), val in Q.items()}
        with open(txt_file, "w") as qd:
            json.dump(jsonifable, qd)

        with open("Q_DEBUG.txt", "w") as f:
            list_of_strings = [f'{key[0]}, {key[1]}: {Q[key]}' for key in Q.keys() if Q[key] is not None]
            [f.write(f'{st}\n') for st in list_of_strings]

    @staticmethod
    def _load_policy(txt_file):
        with open(txt_file, "r") as f:
            policy = json.load(f)
        d = {}
        for key, val in policy.items():
            start, end = key.split(':')
            d[str(start), int(end)] = val
        return d

    @staticmethod
    def _plot_win_ratio(games_won_over_time):
        plt.plot(range(runtime.ITERATIONS), games_won_over_time, color='b')
        plt.xlabel('Iterations')
        plt.ylabel('Games Won')
        plt.title('Number of Games Won Over Time')
        plt.show()
