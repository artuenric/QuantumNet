import random

class Qubit():
    def __init__(self, qubit_id: int, initial_fidelity: float = None) -> None:
        self.qubit_id = qubit_id
        self._qubit_state = 0  # Define the initial qubit state as 0
        self._initial_fidelity = initial_fidelity if initial_fidelity is not None else random.uniform(0, 1)
        self._current_fidelity = self._initial_fidelity

    def __str__(self):
        return f"Qubit {self.qubit_id} with state {self._qubit_state}"

    def get_initial_fidelity(self):
        return self._initial_fidelity

    def get_current_fidelity(self):
        return self._current_fidelity

    def set_current_fidelity(self, new_fidelity: float):
            """Set the current fidelity of the qubit."""
            self._current_fidelity = new_fidelity

    def apply_x(self):
        """Apply X gate (NOT) to the qubit."""
        self._qubit_state = 1 if self._qubit_state == 0 else 0

    def apply_hadamard(self):
        """Apply Hadamard gate (H) to the qubit."""
        # Hadamard transforms state |0> into (|0> + |1>) / sqrt(2)
        # and |1> into (|0> - |1>) / sqrt(2). For simulation, probability is used.
        if self._qubit_state == 0:
            self._qubit_state = random.choice([0, 1])  # Simulates superposition
        else:
            self._qubit_state = random.choice([0, 1])  # Simulates superposition

    def measure(self):
        """Perform measurement of the qubit in its current state."""
        return self._qubit_state
