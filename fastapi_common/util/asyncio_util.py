import asyncio
from typing import Any, Awaitable, Callable, List, Optional


class AsyncIOUtil:
    @staticmethod
    async def gather_tasks(*tasks: Awaitable[Any]) -> List[Any]:
        """
        Run multiple coroutines concurrently and gather their results.
        :param tasks: The coroutines to run.
        :return: A list of results from the coroutines.
        """
        return await asyncio.gather(*tasks)

    @staticmethod
    async def run_with_timeout(coro: Awaitable[Any], timeout: float) -> Any:
        """
        Run an async coroutine with a timeout.
        :param coro: The coroutine to run.
        :param timeout: The timeout in seconds.
        :return: The result of the coroutine if it completes within the timeout.
        :raises asyncio.TimeoutError: If the coroutine does not complete within the timeout.
        """
        try:
            return await asyncio.wait_for(coro, timeout)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"Operation timed out after {timeout} seconds")

    @staticmethod
    async def gather_with_concurrency(limit: int, *tasks: Awaitable[Any]) -> List[Any]:
        """
        Run multiple async tasks with a concurrency limit.
        :param limit: The maximum number of concurrent tasks.
        :param tasks: The async tasks to run.
        :return: A list of results from the tasks.
        """
        semaphore = asyncio.Semaphore(limit)

        async def sem_task(task):
            async with semaphore:
                return await task

        return await asyncio.gather(*(sem_task(task) for task in tasks))

    @staticmethod
    async def retry(
        coro_func: Callable[[], Awaitable[Any]],
        retries: int,
        delay: float,
        exceptions: Optional[tuple] = (Exception,),
    ) -> Any:
        """
        Retry an async function a specified number of times with a delay.
        :param coro_func: The async function to retry.
        :param retries: The number of retry attempts.
        :param delay: The delay between retries in seconds.
        :param exceptions: A tuple of exception types to catch and retry on.
        :return: The result of the coroutine if successful.
        :raises Exception: If all retry attempts fail.
        """
        for attempt in range(retries):
            try:
                return await coro_func()
            except exceptions as e:
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    raise e

    @staticmethod
    async def run_in_executor(func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Run a blocking function in an executor.
        :param func: The blocking function to run.
        :param args: Positional arguments to pass to the function.
        :param kwargs: Keyword arguments to pass to the function.
        :return: The result of the function.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
