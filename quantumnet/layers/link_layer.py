import networkx as nx
from quantumnet.topology import Host
from quantumnet.utils import Logger
from quantumnet.quantum import Epr
from random import uniform

class LinkLayer:
    def __init__(self, context, physical_layer):
        """
        Initialize the link layer.

        Args:
            context (NetworkContext): Shared network context.
            physical_layer (PhysicalLayer): Physical layer.
        """
        self._context = context
        self._physical_layer = physical_layer
        self._requests = []
        self._failed_requests = []
        self.logger = Logger.get_instance()
        self.used_eprs = 0  # Initialize used EPRs counter
        self.used_qubits = 0  # Initialize used qubits counter
        self.created_eprs = []  # Store EPRs created by the physical layer

    @property
    def requests(self):
        return self._requests

    @property
    def failed_requests(self):
        return self._failed_requests

    def __str__(self):
        """ Return the string representation of the link layer.

        Returns:
            str: String representation of the link layer.
        """
        return 'Link Layer'

    def get_used_eprs(self):
        self.logger.debug(f"EPRs used in layer {self.__class__.__name__}: {self.used_eprs}")
        return self.used_eprs

    def get_used_qubits(self):
        self.logger.debug(f"Qubits used in layer {self.__class__.__name__}: {self.used_qubits}")
        return self.used_qubits

    def request(self, alice_id: int, bob_id: int):
        """
        Request entanglement creation between Alice and Bob.

        Args:
            alice_id (int): Alice host ID.
            bob_id (int): Bob host ID.
        """
        try:
            alice = self._context.get_host(alice_id)
            bob = self._context.get_host(bob_id)
        except KeyError:
            self.logger.log(f'Host {alice_id} or {bob_id} not found in network.')
            return False

        for attempt in range(1, self._context.config.protocol.link_max_attempts + 1):
            self._context.clock.emit('link_request_attempt', alice=alice_id, bob=bob_id, attempt=attempt)
            self.logger.log(f'Timeslot {self._context.clock.now}: Entanglement attempt between {alice_id} and {bob_id}.')

            entangle = self._physical_layer.entanglement_creation_heralding_protocol(alice, bob)

            # After each entanglement attempt, transfer created EPRs to the link layer
            if entangle:
                self.used_eprs += 1
                self.used_qubits += 2
                self._requests.append((alice_id, bob_id))

                # Add EPRs created by the physical layer to the link layer's created EPRs list
                if self._physical_layer.created_eprs:
                    self.created_eprs.extend(self._physical_layer.created_eprs)
                    self._physical_layer.created_eprs.clear()  # Clear the physical layer's list

                self.logger.log(f'Timeslot {self._context.clock.now}: Entanglement created between {alice} and {bob} on attempt {attempt}.')
                return True
            else:
                self.logger.log(f'Timeslot {self._context.clock.now}: Entanglement failed between {alice} and {bob} on attempt {attempt}.')
                self._failed_requests.append((alice_id, bob_id))

        # Check if purification should be performed after two failures
        if len(self._failed_requests) >= self._context.config.protocol.link_purification_after_failures:
            purification_success = self.purification(alice_id, bob_id)

            # Regardless of purification success, always transfer created EPRs
            if self._physical_layer.created_eprs:
                self.created_eprs.extend(self._physical_layer.created_eprs)
                self._physical_layer.created_eprs.clear()  # Clear the physical layer's list

            return purification_success

        # After the second attempt, ensure all created EPRs are transferred
        if self._physical_layer.created_eprs:
            self.created_eprs.extend(self._physical_layer.created_eprs)
            self._physical_layer.created_eprs.clear()  # Clear the physical layer's list

        return False

    def purification_calculator(self, f1: int, f2: int, purification_type: int) -> float:
        """
        Purification formula calculation.

        Args:
            f1 (int): Fidelity of the first EPR.
            f2 (int): Fidelity of the second EPR.
            purification_type (int): Chosen formula (1 - Default, 2 - BBPSSW Protocol, 3 - DEJMPS Protocol).

        Returns:
            float: Fidelity after purification.
        """
        f1f2 = f1 * f2

        if purification_type == 1:
            self.logger.log('Purification type 1 was used.')
            return f1f2 / ((f1f2) + ((1 - f1) * (1 - f2)))

        elif purification_type == 2:
            result = (f1f2 + ((1 - f1) / 3) * ((1 - f2) / 3)) / (f1f2 + f1 * ((1 - f2) / 3) + f2 * ((1 - f1) / 3) + 5 * ((1 - f1) / 3) * ((1 - f2) / 3))
            self.logger.log('Purification type 2 was used.')
            return result

        elif purification_type == 3:
            result = (2 * f1f2 + 1 - f1 - f2) / ((1 / 4) * (f1 + f2 - f1f2) + 3 / 4)
            self.logger.log('Purification type 3 was used.')
            return result

        self.logger.log('Purification only accepts values (1, 2, or 3), formula 1 was chosen by default.')
        return f1f2 / ((f1f2) + ((1 - f1) * (1 - f2)))


    def purification(self, alice_id: int, bob_id: int, purification_type: int = 1):
        """
        EPR purification.

        Args:
            alice_id (int): Alice host ID.
            bob_id (int): Bob host ID.
            purification_type (int): Purification protocol type.
        """
        self._context.clock.tick()

        eprs_fail = self._physical_layer.failed_eprs

        if len(eprs_fail) < 2:
            self.logger.log(f'Timeslot {self._context.clock.now}: Not enough EPRs for purification on channel ({alice_id}, {bob_id}).')
            return False

        eprs_fail1 = eprs_fail[-1]
        eprs_fail2 = eprs_fail[-2]
        f1 = eprs_fail1.get_current_fidelity()
        f2 = eprs_fail2.get_current_fidelity()

        purification_prob = (f1 * f2) + ((1 - f1) * (1 - f2))

        # Increment used EPRs count, as both will be used in the purification attempt
        self.used_eprs += 2
        self.used_qubits += 4

        if purification_prob > self._context.config.fidelity.purification_min_probability:
            new_fidelity = self.purification_calculator(f1, f2, purification_type)

            if new_fidelity > self._context.config.fidelity.purification_threshold:
                epr_purified = Epr((alice_id, bob_id), new_fidelity)
                self._physical_layer.add_epr_to_channel(epr_purified, (alice_id, bob_id))
                self._physical_layer.failed_eprs.remove(eprs_fail1)
                self._physical_layer.failed_eprs.remove(eprs_fail2)
                self.logger.log(f'Used EPRs {self.used_eprs}')
                self._context.clock.emit('purification_success', alice=alice_id, bob=bob_id, fidelity=new_fidelity)
                self.logger.log(f'Timeslot {self._context.clock.now}: Purification succeeded on channel ({alice_id}, {bob_id}) with new fidelity {new_fidelity}.')
                return True
            else:
                self._physical_layer.failed_eprs.remove(eprs_fail1)
                self._physical_layer.failed_eprs.remove(eprs_fail2)
                self._context.clock.emit('purification_failed', alice=alice_id, bob=bob_id, reason='low_fidelity')
                self.logger.log(f'Timeslot {self._context.clock.now}: Purification failed on channel ({alice_id}, {bob_id}) due to low fidelity after purification.')
                return False
        else:
            self._physical_layer.failed_eprs.remove(eprs_fail1)
            self._physical_layer.failed_eprs.remove(eprs_fail2)
            self._context.clock.emit('purification_failed', alice=alice_id, bob=bob_id, reason='low_probability')
            self.logger.log(f'Timeslot {self._context.clock.now}: Purification failed on channel ({alice_id}, {bob_id}) due to low purification success probability.')
            return False

    def avg_fidelity_on_linklayer(self):
        """
        Calculate the average fidelity of EPRs created in the link layer.

        Returns:
            float: Average fidelity of link layer EPRs.
        """
        total_fidelity = 0
        total_eprs = len(self.created_eprs)

        for epr in self.created_eprs:
            total_fidelity += epr.get_current_fidelity()

        if total_eprs == 0:
            self.logger.log('No EPRs created in the link layer.')
            return 0


        self.logger.debug(f'Total EPRs created in the link layer: {total_eprs}')
        self.logger.debug(f'Total fidelity of EPRs created in the link layer: {total_fidelity}')
        avg_fidelity = total_fidelity / total_eprs
        self.logger.log(f'The average fidelity of EPRs created in the link layer is {avg_fidelity}')
        return avg_fidelity
