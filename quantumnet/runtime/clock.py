class Clock:
    """
    Centralized clock for quantum network simulation.

    Responsible for:
    - Tracking the current timeslot (now)
    - Advancing time via tick(), firing registered callbacks
    - Recording events via emit(), without advancing time
    - Maintaining a complete event history (history)
    """

    def __init__(self):
        self._timeslot = 0
        self._history = []
        self._on_tick_callbacks = []
        self._event_callbacks = {}

    @property
    def now(self) -> int:
        """Return the current timeslot."""
        return self._timeslot

    @property
    def history(self) -> list:
        """Return the complete event history."""
        return list(self._history)

    def tick(self, cost: int = 1):
        """
        Advance time by 'cost' timeslots.
        For each unit of advancement, fires all registered on_tick callbacks.

        Args:
            cost (int): Number of timeslots to advance. Default: 1.
        """
        for _ in range(cost):
            self._timeslot += 1
            for callback in self._on_tick_callbacks:
                callback(self)

    def emit(self, event_name: str, **data):
        """
        Record an event in the history at the current timeslot, without advancing time.
        Fires callbacks registered for the specific event.

        Args:
            event_name (str): Event name.
            **data: Additional event data.
        """
        entry = {'timeslot': self._timeslot, 'event': event_name, **data}
        self._history.append(entry)
        if event_name in self._event_callbacks:
            for callback in self._event_callbacks[event_name]:
                callback(self, **data)

    def on_tick(self, callback):
        """
        Register a callback to be called on each tick.
        The callback receives the clock as argument: callback(clock).

        Args:
            callback: Function to be called on each tick.
        """
        self._on_tick_callbacks.append(callback)

    def on(self, event_name: str, callback):
        """
        Register a callback to react to a specific event.
        The callback receives the clock and event data: callback(clock, **data).

        Args:
            event_name (str): Event name.
            callback: Function to be called when the event occurs.
        """
        if event_name not in self._event_callbacks:
            self._event_callbacks[event_name] = []
        self._event_callbacks[event_name].append(callback)
