from .base_source import ManualFirstWebSource


class FomaSource(ManualFirstWebSource):
    def __init__(self):
        super().__init__("Foma", "https://foma.ru/")

