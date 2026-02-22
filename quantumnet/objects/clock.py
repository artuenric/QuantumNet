class Clock:
    """
    Relógio centralizado para a simulação de rede quântica.

    Responsável por:
    - Rastrear o timeslot atual (now)
    - Avançar o tempo via tick(), disparando callbacks registrados
    - Registrar eventos via emit(), sem avançar o tempo
    - Manter um histórico completo de eventos (history)
    """

    def __init__(self):
        self._timeslot = 0
        self._history = []
        self._on_tick_callbacks = []
        self._event_callbacks = {}

    @property
    def now(self) -> int:
        """Retorna o timeslot atual."""
        return self._timeslot

    @property
    def history(self) -> list:
        """Retorna o histórico completo de eventos."""
        return list(self._history)

    def tick(self, cost: int = 1):
        """
        Avança o tempo em 'cost' timeslots.
        Para cada unidade de avanço, dispara todos os callbacks on_tick registrados.

        Args:
            cost (int): Número de timeslots a avançar. Padrão: 1.
        """
        for _ in range(cost):
            self._timeslot += 1
            for callback in self._on_tick_callbacks:
                callback(self)

    def emit(self, event_name: str, **data):
        """
        Registra um evento no histórico no timeslot atual, sem avançar o tempo.
        Dispara callbacks registrados para o evento específico.

        Args:
            event_name (str): Nome do evento.
            **data: Dados adicionais do evento.
        """
        entry = {'timeslot': self._timeslot, 'event': event_name, **data}
        self._history.append(entry)
        if event_name in self._event_callbacks:
            for callback in self._event_callbacks[event_name]:
                callback(self, **data)

    def on_tick(self, callback):
        """
        Registra um callback a ser chamado a cada tick.
        O callback recebe o clock como argumento: callback(clock).

        Args:
            callback: Função a ser chamada a cada tick.
        """
        self._on_tick_callbacks.append(callback)

    def on(self, event_name: str, callback):
        """
        Registra um callback para reagir a um evento específico.
        O callback recebe o clock e os dados do evento: callback(clock, **data).

        Args:
            event_name (str): Nome do evento.
            callback: Função a ser chamada quando o evento ocorre.
        """
        if event_name not in self._event_callbacks:
            self._event_callbacks[event_name] = []
        self._event_callbacks[event_name].append(callback)
