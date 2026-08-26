from .base_source import ManualFirstWebSource


class AzbykaSource(ManualFirstWebSource):
    def __init__(self):
        super().__init__("Azbyka", "https://azbyka.ru/days/")

