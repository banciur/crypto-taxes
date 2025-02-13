class KrakenImporter:

    def __init__(self, source_path:str) -> None:
        self.source_path = source_path

    def process_file(self) -> None:
        print(self.source_path)
