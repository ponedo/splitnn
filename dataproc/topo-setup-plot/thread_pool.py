from concurrent.futures import ThreadPoolExecutor, as_completed

class ThreadPool:
    def __init__(self, max_workers=8):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = []

    def add_task(self, func, *args, **kwargs):
        """
        Adds a task to the thread pool.
        :param func: The function to execute.
        :param args: Positional arguments for the function.
        :param kwargs: Keyword arguments for the function.
        """
        future = self.executor.submit(func, *args, **kwargs)
        self.futures.append(future)

    def wait_for_completion(self):
        """
        Waits for all submitted tasks to complete and returns their results.
        :return: A list of results from completed tasks.
        """
        results = []
        for future in as_completed(self.futures):
            try:
                results.append(future.result())
            except Exception as e:
                results.append(f"Error: {e}")
        return results

    def shutdown(self):
        """Shuts down the thread pool."""
        self.executor.shutdown(wait=True)

