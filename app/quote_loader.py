from PySide6.QtCore import QThread, Signal


class QuoteLoaderThread(QThread):
    quotes_loaded = Signal(list, int)

    def __init__(
        self,
        *,
        query,
        storage,
        start_idx,
        end_idx,
        search_version,
        filters=None,
    ):
        super().__init__()

        self.query = query
        self.storage = storage
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.search_version = search_version
        self.filters = filters or {}

    def run(self):
        from .search import search_quotes

        # canonical search
        results = search_quotes(
            self.storage,
            self.query,
            filters=self.filters
        )

        if self.isInterruptionRequested():
            return

        # paginate
        page = results[self.start_idx : self.end_idx]

        self.quotes_loaded.emit(page, self.search_version)