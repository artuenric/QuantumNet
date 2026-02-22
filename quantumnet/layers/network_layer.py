import networkx as nx
from quantumnet.topology import Host
from quantumnet.utils import Logger
from quantumnet.quantum import Epr
from random import uniform

class NetworkLayer:
    def __init__(self, context, physical_layer):
        """
        Initialize the network layer.

        Args:
            context (NetworkContext): Shared network context.
            physical_layer (PhysicalLayer): Physical layer.
        """
        self._context = context
        self._physical_layer = physical_layer
        self.logger = Logger.get_instance()
        self.avg_size_routes = 0  # Initialize average route size
        self.used_eprs = 0  # Initialize used EPRs counter
        self.used_qubits = 0  # Initialize used qubits counter
        self.routes_used = {}  # Initialize used routes dictionary
    def __str__(self):
        """ Return the string representation of the network layer.

        Returns:
            str: String representation of the network layer."""
        return 'Network Layer'

    def get_used_eprs(self):
        """Return the count of EPRs used in the network layer."""
        self.logger.debug(f"EPRs used in layer {self.__class__.__name__}: {self.used_eprs}")
        return self.used_eprs

    def get_used_qubits(self):
        self.logger.debug(f"Qubits used in layer {self.__class__.__name__}: {self.used_qubits}")
        return self.used_qubits

    def short_route_valid(self, Alice: int, Bob: int) -> list:
        """
        Choose the best route between two hosts with additional criteria.

        Args:
            Alice (int): Source host ID.
            Bob (int): Destination host ID.

        Returns:
            list or None: List with the best route between hosts or None if no valid route exists.
        """
        self._context.clock.emit('route_lookup', alice=Alice, bob=Bob)
        self.logger.log(f'Timeslot {self._context.clock.now}: Looking for valid route between {Alice} and {Bob}.')

        if Alice is None or Bob is None:
            self.logger.log('Invalid host IDs provided.')
            return None

        if not self._context.graph.has_node(Alice) or not self._context.graph.has_node(Bob):
            self.logger.log(f'One of the nodes ({Alice} or {Bob}) does not exist in the graph.')
            return None

        try:
            all_shortest_paths = list(nx.all_shortest_paths(self._context.graph, Alice, Bob))
        except nx.NetworkXNoPath:
            self.logger.log(f'No route found between {Alice} and {Bob}')
            return None

        for path in all_shortest_paths:
            valid_path = True
            for i in range(len(path) - 1):
                node = path[i]
                next_node = path[i + 1]
                if len(self._context.get_eprs_from_edge(node, next_node)) < 1:
                    self.logger.log(f'No EPR pairs between {node} and {next_node} in route {path}')
                    valid_path = False
                    break

            if valid_path:
                self.logger.log(f'Valid route found: {path}')

                # Store the route if it's the first time it's used
                if (Alice, Bob) not in self.routes_used:
                    self.routes_used[(Alice, Bob)] = path.copy()

                return path

        self.logger.log('No valid route found.')
        return None



    def entanglement_swapping(self, Alice: int = None, Bob: int = None) -> bool:
        """
        Perform Entanglement Swapping across the entire route determined by short_route_valid.

        Args:
            Alice (int, optional): Source host ID. If not provided, uses the first node of the valid route.
            Bob (int, optional): Destination host ID. If not provided, uses the last node of the valid route.

        Returns:
            bool: True if all Entanglement Swappings succeeded, False otherwise.
        """
        # Get valid route between Alice and Bob using short_route_valid
        route = self.short_route_valid(Alice, Bob)

        # Check if a valid route was found and has at least 2 nodes
        if route is None or len(route) < 2:
            self.logger.log('Could not determine a valid route.')
            return False

        # Define Alice and Bob as the first and last nodes of the route
        Alice = route[0]
        Bob = route[-1]

        # Iterate over the route performing entanglement swapping for each segment
        while len(route) > 1:
            # Increment timeslot before each entanglement swapping operation
            self._context.clock.tick()
            self.logger.log(f'Timeslot {self._context.clock.now}: Performing Entanglement Swapping.')

            node1 = route[0]    # First node in route
            node2 = route[1]    # Second node in route
            node3 = route[2] if len(route) > 2 else None  # Third node in route (if exists)

            # Check if a channel exists between node1 and node2
            if not self._context.graph.has_edge(node1, node2):
                self.logger.log(f'Channel between {node1}-{node2} does not exist')
                return False

            try:
                # Get the first EPR pair between node1 and node2
                epr1 = self._context.get_eprs_from_edge(node1, node2)[0]
            except IndexError:
                # If there are not enough EPR pairs, log the failure and return False
                self.logger.log(f'Not enough EPR pairs between {node1}-{node2}')
                return False

            # If there is a third node, perform swapping between node1, node2, and node3
            if node3 is not None:
                # Check if a channel exists between node2 and node3
                if not self._context.graph.has_edge(node2, node3):
                    self.logger.log(f'Channel between {node2}-{node3} does not exist')
                    return False

                try:
                    # Get the first EPR pair between node2 and node3
                    epr2 = self._context.get_eprs_from_edge(node2, node3)[0]
                except IndexError:
                    # If there are not enough EPR pairs, log the failure and return False
                    self.logger.log(f'Not enough EPR pairs between {node2}-{node3}')
                    return False

                # Measure fidelity of EPR pairs
                fidelity1 = epr1.get_current_fidelity()
                fidelity2 = epr2.get_current_fidelity()

                # Calculate entanglement swapping success probability
                success_prob = fidelity1 * fidelity2 + (1 - fidelity1) * (1 - fidelity2)

                # Check if swapping succeeded based on success probability
                if uniform(0, 1) > success_prob:
                    self.logger.log(f'Entanglement Swapping failed between {node1}-{node2} and {node2}-{node3}')
                    return False

                # Calculate the new virtual EPR pair fidelity
                new_fidelity = (fidelity1 * fidelity2) / ((fidelity1 * fidelity2) + (1 - fidelity1) * (1 - fidelity2))
                epr_virtual = Epr((node1, node3), new_fidelity)

                # If the channel between node1 and node3 doesn't exist, add a new channel
                if not self._context.graph.has_edge(node1, node3):
                    self._context.graph.add_edge(node1, node3, eprs=[])

                # Add virtual EPR pair to the channel between node1 and node3
                self._physical_layer.add_epr_to_channel(epr_virtual, (node1, node3))
                # Remove old EPR pairs from channels between node1-node2 and node2-node3
                self._physical_layer.remove_epr_from_channel(epr1, (node1, node2))
                self._physical_layer.remove_epr_from_channel(epr2, (node2, node3))

                # Update used EPRs counter
                self.used_eprs += 1

                # Remove the second node from the route, as swapping was performed
                route.pop(1)
            else:
                # If there's no third node, just remove the second node from the route
                route.pop(1)

        # Log entanglement swapping success
        self._context.clock.emit('entanglement_swapping_complete', alice=Alice, bob=Bob)
        self.logger.log(f'Entanglement Swapping completed successfully between {Alice} and {Bob}')
        return True

    def get_avg_size_routes(self):
        """
        Calculate the average size of used routes, considering the number of hops (edges) between nodes.

        Returns:
            float: Average size of used routes.
        """
        total_size = 0
        num_routes = 0

        # Iterate over routes stored in the dictionary
        for route in self.routes_used.values():
            total_size += len(route) - 1  # Sum the number of edges (hops), which is number of nodes minus 1
            num_routes += 1  # Count the number of routes

        # Calculate the average if there are valid routes
        if num_routes > 0:
            self.avg_size_routes = total_size / num_routes
        else:
            # Return 0 if there are no valid routes
            self.avg_size_routes = 0.0

        return self.avg_size_routes
