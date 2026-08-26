from .base_source import ManualFirstWebSource


class PatriarchiaSource(ManualFirstWebSource):
    def __init__(self):
        super().__init__("Moscow Patriarchate", "https://www.patriarchia.ru/")

