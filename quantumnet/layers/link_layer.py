from ..utils import Logger

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
        self._failed_request_count = 0
        self.logger = Logger.get_instance()

    @property
    def failed_request_count(self):
        return self._failed_request_count

    def __str__(self):
        """ Return the string representation of the link layer.

        Returns:
            str: String representation of the link layer.
        """
        return 'Link Layer'

    def request(self, alice_id: int, bob_id: int, high_fidelity: bool = True, on_complete=None):
        """
        Schedule entanglement creation between Alice and Bob. Fire-and-forget.

        Result communicated via:
          - 'link_request_success' or 'link_request_failed' event
          - on_complete(success=True/False) callback if provided

        Args:
            alice_id (int): Alice host ID.
            bob_id (int): Bob host ID.
            high_fidelity (bool): If True (default), only accept EPR pairs above the
                fidelity threshold and attempt purification on failure. If False,
                accept any successfully created EPR pair regardless of fidelity.
            on_complete: Optional callback(success=bool).
        """
        self._start_attempt(alice_id, bob_id, attempt=1, failures=0, high_fidelity=high_fidelity, on_complete=on_complete)

    def _start_attempt(self, alice_id, bob_id, attempt, failures, high_fidelity, on_complete):
        """Schedule the next heralding attempt or give up."""
        max_attempts = self._context.config.protocol.link_max_attempts

        if attempt > max_attempts:
            self._context.clock.emit('link_request_failed',
                                      alice=alice_id, bob=bob_id)
            if on_complete is not None:
                on_complete(success=False)
            return

        try:
            alice = self._context.get_host(alice_id)
            bob = self._context.get_host(bob_id)
        except KeyError:
            self.logger.log(f'Host {alice_id} or {bob_id} not found in network.')
            if on_complete is not None:
                on_complete(success=False)
            return

        self._context.clock.emit('link_request_attempt',
                                  alice=alice_id, bob=bob_id, attempt=attempt)
        self.logger.log(f'Timeslot {self._context.clock.now}: Entanglement attempt between {alice_id} and {bob_id}.')

        # Define what happens when heralding completes
        def on_heralding_done(success, epr_fidelity=None):
            if success:
                self.logger.log(f'{self.__class__.__name__}: 1 EPR used')
                self.logger.log(f'{self.__class__.__name__}: 2 qubits used')
                self.logger.log(f'Timeslot {self._context.clock.now}: Entanglement created between {alice_id} and {bob_id} on attempt {attempt}.')
                self._context.clock.emit('link_request_success',
                                          alice=alice_id, bob=bob_id, fidelity=epr_fidelity)
                if on_complete is not None:
                    on_complete(success=True)
            else:
                self.logger.log(f'Timeslot {self._context.clock.now}: Entanglement failed between {alice_id} and {bob_id} on attempt {attempt}.')
                self._failed_request_count += 1
                # Retry: schedule next attempt
                self._start_attempt(alice_id, bob_id, attempt + 1, failures + 1, high_fidelity, on_complete)

        # Schedule heralding (async, result comes via on_heralding_done)
        self._physical_layer.entanglement_creation_heralding_protocol(
            alice, bob, high_fidelity=high_fidelity, on_complete=on_heralding_done
        )

    def purification(self, alice_id: int, bob_id: int, purification_type: int = 1, on_complete=None):
        """
        Purification protocol: consumes two EPR pairs from the channel and
        replaces them with one higher-fidelity pair.

        Result communicated via:
          - 'purification_success' or 'purification_failed' event
          - on_complete(success=True/False) callback if provided

        Args:
            alice_id (int): Alice host ID.
            bob_id (int): Bob host ID.
            purification_type (int): Protocol variant (1=Default, 2=BBPSSW, 3=DEJMPS).
            on_complete: Optional callback(success=bool).
        """
        def _run():
            eprs = self._context.get_eprs_from_edge(alice_id, bob_id)
            if len(eprs) < 2:
                self._context.clock.emit('purification_failed',
                                          alice=alice_id, bob=bob_id, reason='insufficient_eprs')
                if on_complete is not None:
                    on_complete(success=False)
                return

            epr1, epr2 = eprs[-1], eprs[-2]
            self._physical_layer.remove_epr_from_channel(epr1, (alice_id, bob_id))
            self._physical_layer.remove_epr_from_channel(epr2, (alice_id, bob_id))

            f_purified = self.purification_calculator(
                epr1.current_fidelity, epr2.current_fidelity, purification_type
            )
            epr_new = self._physical_layer.create_epr_pair(fidelity=f_purified)
            self._physical_layer.add_epr_to_channel(epr_new, (alice_id, bob_id))

            self._context.clock.emit('purification_success',
                                      alice=alice_id, bob=bob_id, fidelity=f_purified)
            if on_complete is not None:
                on_complete(success=True)

        self._context.clock.schedule(1, _run)

    def purification_calculator(self, f1: float, f2: float, purification_type: int) -> float:
        """
        Purification formula calculation.

        Args:
            f1 (float): Fidelity of the first EPR.
            f2 (float): Fidelity of the second EPR.
            purification_type (int): Chosen formula (1 - Default, 2 - BBPSSW Protocol, 3 - DEJMPS Protocol).

        Returns:
            float: Fidelity after purification.
        """
        f1f2 = f1 * f2
        # Bit-flip
        if purification_type == 1:
            self.logger.log('Purification type 1 was used.')
            return f1f2 / ((f1f2) + ((1 - f1) * (1 - f2)))
        # BBPSSW
        elif purification_type == 2:
            result = (f1f2 + ((1 - f1) / 3) * ((1 - f2) / 3)) / (f1f2 + f1 * ((1 - f2) / 3) + f2 * ((1 - f1) / 3) + 5 * ((1 - f1) / 3) * ((1 - f2) / 3))
            self.logger.log('Purification type 2 was used.')
            return result
        #DEJMPS
        elif purification_type == 3:
            result = (2 * f1f2 + 1 - f1 - f2) / ((1 / 4) * (f1 + f2 - f1f2) + 3 / 4)
            self.logger.log('Purification type 3 was used.')
            return result

        self.logger.log('Purification only accepts values (1, 2, or 3), formula 1 was chosen by default.')
        return f1f2 / ((f1f2) + ((1 - f1) * (1 - f2)))

