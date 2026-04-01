import json
import numpy as np
from ase.parallel import world, DummyMPI


class Moveset:
    def __init__(
        self,
        moves=None,
        restart_file=None,
        communicator=world,
        rng=None,
        append_trajectory=False,
    ):
        if communicator is None:
            communicator = DummyMPI()
        self.communicator = communicator
        if rng is None:
            self.rng = np.random
        else:
            self.rng = rng

        self.moves = moves
        self.restart_file = restart_file
        self.current_move = None
        self.normalize_move_probabilities()

    def normalize_move_probabilities(self):
        move_probs = np.zeros(len(self.moves))
        for i, move in enumerate(self.moves):
            move_probs[i] = move.probability
        self.move_probs = move_probs / np.sum(move_probs)

    def add_move(self, move):
        self.moves += move
        self.normalize_move_probabilities()

    def pick_move(self, atoms):
        # If the length of atoms object is 0, we have to attempt an Insert or swap move
        if len(atoms) == 0:
            for move in self.moves:
                if move.name == "Insert":
                    self.current_move = move
        else:
            # We have to do random numbers as numpy arrays like this for broadcasting
            idx_arr = np.array(
                [self.rng.choice(np.arange(len(self.moves)), p=self.move_probs)]
            )
            self.communicator.broadcast(idx_arr, 0)
            self.current_move = self.moves[idx_arr[0]]

    def save_moves(self):
        pass

    def execute_move(self, atoms, results_o):
        accepted, results = self.current_move.execute(atoms, results_o)
        return accepted, results

    def get_current_move_stats(self):
        if self.current_move is None:
            return "Initializing"
        else:
            return self.current_move.get_move_stats()

    def adjust_parameter(
        self,
        move,
        parameter,
        value,
        normalize_probabilities=True,
        species_tag=None,
        verbose=False,
    ):
        # Find the move in the move list
        move_idx = -1
        for i, mcmove in enumerate(self.moves):
            name = type(mcmove).__name__
            if name == move:
                if name == "Chemical":
                    if mcmove.species_tag == species_tag:
                        move_idx = i
                else:
                    move_idx = i

        if move_idx == -1:
            if verbose:
                if move == "Insert" or "Delete":
                    print(
                        f"Move {move} found in moveset for species tag {species_tag}."
                    )
                else:
                    print(f"Move {move} not found in moveset.")

        else:
            if verbose:
                old_value = getattr(self.moves[move_idx], parameter)
                if move == "Insert" or "Delete":
                    print(
                        f"Move {move} found in moveset for species tag {species_tag}."
                    )
                else:
                    print(f"Move {move} found in moveset.")
                print(f"Adjusting parameter {parameter} from {old_value} to {value}")
            setattr(self.moves[move_idx], parameter, value)
            if normalize_probabilities:
                self.normalize_move_probabilities()

