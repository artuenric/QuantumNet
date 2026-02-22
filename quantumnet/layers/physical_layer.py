from ..utils import Logger
from ..quantum import Qubit, Epr
from ..topology import Host
from random import uniform
import random

class PhysicalLayer:
    def __init__(self, context, physical_layer_id: int = 0):
        """
        Initialize the physical layer.

        Args:
            context (NetworkContext): Shared network context.
            physical_layer_id (int): Physical layer ID.
        """
        self._physical_layer_id = physical_layer_id
        self._context = context
        self._failed_eprs = []
        self.created_eprs = []  # List to store all created EPRs
        self._count_qubit = 0
        self._count_epr = 0
        self.logger = Logger.get_instance()
        self.used_eprs = 0
        self.used_qubits = 0


    def __str__(self):
        """ Return the string representation of the physical layer.

        Returns:
            str: String representation of the physical layer.
        """
        return f'Physical Layer {self.physical_layer_id}'

    @property
    def physical_layer_id(self):
        """Return the physical layer ID.

        Returns:
            int: Physical layer ID.
        """
        return self._physical_layer_id

    @property
    def failed_eprs(self):
        """Return the failed EPR pairs.

        Returns:
            dict: Dictionary of failed EPR pairs.
        """
        return self._failed_eprs

    def get_used_eprs(self):
        self.logger.debug(f"EPRs used in layer {self.__class__.__name__}: {self.used_eprs}")
        return self.used_eprs

    def get_used_qubits(self):
        self.logger.debug(f"Qubits used in layer {self.__class__.__name__}: {self.used_qubits}")
        return self.used_qubits

    def create_qubit(self, host_id: int, increment_qubits: bool = True):
        """Create a qubit and add it to the specified host's memory.

        Args:
            host_id (int): ID of the host where the qubit will be created.
            increment_qubits (bool): If True, increments the used qubits counter.

        Raises:
            Exception: If the specified host does not exist in the network.
        """
        if increment_qubits:
            self.used_qubits += 1

        if host_id not in self._context.hosts:
            raise Exception(f'Host {host_id} does not exist in the network.')

        qubit_id = self._count_qubit
        qubit = Qubit(qubit_id)
        self._context.hosts[host_id].add_qubit(qubit)

        self._context.register_qubit_creation(qubit_id, "Physical Layer")

        self._count_qubit += 1
        self._context.clock.emit('qubit_created', host_id=host_id, qubit_id=qubit_id)
        self.logger.debug(f'Qubit {qubit_id} created with initial fidelity {qubit.get_initial_fidelity()} and added to memory of Host {host_id}.')

    def create_epr_pair(self, fidelity: float = 1.0, increment_eprs: bool = True):
        """Create an entangled qubit pair.

        Returns:
            Epr: Created EPR pair.
        """
        if increment_eprs:
            self.used_eprs += 1

        epr = Epr(self._count_epr, fidelity)
        self._count_epr += 1
        self._context.clock.emit('epr_created', epr_id=epr.epr_id, fidelity=fidelity)
        return epr

    def add_epr_to_channel(self, epr: Epr, channel: tuple):
        """Add an EPR pair to the channel.

        Args:
            epr (Epr): EPR pair.
            channel (tuple): Channel.
        """
        u, v = channel
        if not self._context.graph.has_edge(u, v):
            self._context.graph.add_edge(u, v, eprs=[])
        self._context.graph.edges[u, v]['eprs'].append(epr)
        self.logger.debug(f'EPR pair {epr} added to channel {channel}.')

    def remove_epr_from_channel(self, epr: Epr, channel: tuple):
        """Remove an EPR pair from the channel.

        Args:
            epr (Epr): EPR pair to be removed.
            channel (tuple): Channel.
        """
        u, v = channel
        if not self._context.graph.has_edge(u, v):
            self.logger.debug(f'Channel {channel} does not exist.')
            return
        try:
            self._context.graph.edges[u, v]['eprs'].remove(epr)
            self.logger.debug(f'EPR pair {epr} removed from channel {channel}.')
        except ValueError:
            self.logger.debug(f'EPR pair {epr} not found in channel {channel}.')

    def fidelity_measurement_only_one(self, qubit: Qubit):
        """Measure the fidelity of a qubit.

        Args:
            qubit (Qubit): Qubit.

        Returns:
            float: Qubit fidelity.
        """
        fidelity = qubit.get_current_fidelity()

        if self._context.clock.now > 0:
            # Apply decoherence factor per measurement
            new_fidelity = max(0, fidelity * self._context.config.decoherence.per_measurement)
            qubit.set_current_fidelity(new_fidelity)
            self.logger.log(f'The fidelity of qubit {qubit} is {new_fidelity}')
            return new_fidelity

        self.logger.log(f'The fidelity of qubit {qubit} is {fidelity}')
        return fidelity

    def fidelity_measurement(self, qubit1: Qubit, qubit2: Qubit):
        """Measure and apply decoherence to two qubits, and log the result."""
        fidelity1 = self.fidelity_measurement_only_one(qubit1)
        fidelity2 = self.fidelity_measurement_only_one(qubit2)
        combined_fidelity = fidelity1 * fidelity2
        self.logger.log(f'The fidelity between qubit {fidelity1} and qubit {fidelity2} is {combined_fidelity}')
        return combined_fidelity

    def entanglement_creation_heralding_protocol(self, alice: Host, bob: Host):
        """Entanglement creation heralding protocol.

        Returns:
            bool: True if the protocol succeeded, False otherwise.
        """
        self._context.clock.tick()
        self.used_qubits += 2

        qubit1 = alice.get_last_qubit()
        qubit2 = bob.get_last_qubit()

        q1 = qubit1.get_current_fidelity()
        q2 = qubit2.get_current_fidelity()

        epr_fidelity = q1 * q2
        self.logger.log(f'Timeslot {self._context.clock.now}: EPR pair created with fidelity {epr_fidelity}')
        epr = self.create_epr_pair(epr_fidelity)

        # Store the created EPR in the created EPRs list
        self.created_eprs.append(epr)

        alice_host_id = alice.host_id
        bob_host_id = bob.host_id

        if epr_fidelity >= self._context.config.fidelity.epr_threshold:
            # If fidelity is adequate, add EPR to the network channel
            self._context.graph.edges[(alice_host_id, bob_host_id)]['eprs'].append(epr)
            self._context.clock.emit('echp_success', alice=alice_host_id, bob=bob_host_id, fidelity=epr_fidelity)
            self.logger.log(f'Timeslot {self._context.clock.now}: Entanglement creation protocol succeeded with required fidelity.')
            return True
        else:
            # Add EPR to channel even with low fidelity
            self._context.graph.edges[(alice_host_id, bob_host_id)]['eprs'].append(epr)
            self._failed_eprs.append(epr)
            self._context.clock.emit('echp_low_fidelity', alice=alice_host_id, bob=bob_host_id, fidelity=epr_fidelity)
            self.logger.log(f'Timeslot {self._context.clock.now}: Entanglement creation protocol succeeded, but with low fidelity.')
            return False

    def echp_on_demand(self, alice_host_id: int, bob_host_id: int):
        """Protocol for recreating entanglement between qubits based on the on-demand EPR pair creation success probability.

        Args:
            alice_host_id (int): Alice Host ID.
            bob_host_id (int): Bob Host ID.

        Returns:
            bool: True if the protocol succeeded, False otherwise.
        """
        self._context.clock.tick()
        self.used_qubits += 2

        qubit1 = self._context.hosts[alice_host_id].get_last_qubit()
        qubit2 = self._context.hosts[bob_host_id].get_last_qubit()

        fidelity_qubit1 = self.fidelity_measurement_only_one(qubit1)
        fidelity_qubit2 = self.fidelity_measurement_only_one(qubit2)

        prob_on_demand_epr_create = self._context.graph.edges[alice_host_id, bob_host_id]['prob_on_demand_epr_create']
        echp_success_probability = prob_on_demand_epr_create * fidelity_qubit1 * fidelity_qubit2

        if uniform(0, 1) < echp_success_probability:
            self.logger.log(f'Timeslot {self._context.clock.now}: EPR pair created with fidelity {fidelity_qubit1 * fidelity_qubit2}')
            epr = self.create_epr_pair(fidelity_qubit1 * fidelity_qubit2)
            self._context.graph.edges[alice_host_id, bob_host_id]['eprs'].append(epr)
            self._context.clock.emit('echp_on_demand_success', alice=alice_host_id, bob=bob_host_id)
            self.logger.log(f'Timeslot {self._context.clock.now}: ECHP success probability is {echp_success_probability}')
            return True
        self._context.clock.emit('echp_on_demand_failed', alice=alice_host_id, bob=bob_host_id)
        self.logger.log(f'Timeslot {self._context.clock.now}: ECHP success probability failed.')
        return False

    def echp_on_replay(self, alice_host_id: int, bob_host_id: int):
        """Protocol for recreating entanglement between qubits that were already losing their characteristics.

        Args:
            alice_host_id (int): Alice Host ID.
            bob_host_id (int): Bob Host ID.

        Returns:
            bool: True if the protocol succeeded, False otherwise.
        """
        self._context.clock.tick()
        self.used_qubits += 2

        qubit1 = self._context.hosts[alice_host_id].get_last_qubit()
        qubit2 = self._context.hosts[bob_host_id].get_last_qubit()

        fidelity_qubit1 = self.fidelity_measurement_only_one(qubit1)
        fidelity_qubit2 = self.fidelity_measurement_only_one(qubit2)

        prob_replay_epr_create = self._context.graph.edges[alice_host_id, bob_host_id]['prob_replay_epr_create']
        echp_success_probability = prob_replay_epr_create * fidelity_qubit1 * fidelity_qubit2

        if uniform(0, 1) < echp_success_probability:
            self.logger.log(f'Timeslot {self._context.clock.now}: EPR pair created with fidelity {fidelity_qubit1 * fidelity_qubit2}')
            epr = self.create_epr_pair(fidelity_qubit1 * fidelity_qubit2)
            self._context.graph.edges[alice_host_id, bob_host_id]['eprs'].append(epr)
            self._context.clock.emit('echp_on_replay_success', alice=alice_host_id, bob=bob_host_id)
            self.logger.log(f'Timeslot {self._context.clock.now}: ECHP success probability is {echp_success_probability}')
            return True
        self._context.clock.emit('echp_on_replay_failed', alice=alice_host_id, bob=bob_host_id)
        self.logger.log(f'Timeslot {self._context.clock.now}: ECHP success probability failed.')
        return False
