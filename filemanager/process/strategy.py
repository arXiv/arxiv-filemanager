"""File checks."""

from functools import partial
from queue import Queue
from threading import Thread
from typing import Optional, Callable, List, Tuple, Iterable

from flask import Flask

from arxiv.base import logging
from .check.base import StopCheck
from ..domain import Workspace, IChecker, ICheckingStrategy, \
    UserFile

logger = logging.getLogger(__name__)
logger.propagate = False


class BaseCheckingStrategy:
    """Base class for checking strategies."""
    pass


class Worker(Thread):
    """A worker thread that executes tasks from a queue."""

    def __init__(self, tasks: Queue) -> None:
        Thread.__init__(self)
        self.tasks = tasks
        self.daemon = True
        self.start()

    def run(self) -> None:
        """Perform tasks until the queue is empty."""
        while True:
            func, args = self.tasks.get()
            try:
                func(*args)
            except Exception as e:
                print(e)
            finally:
                # Mark this task as done, whether an exception happened or not.
                self.tasks.task_done()


class ThreadPool:
    """Manages a pool of :class:`.Worker` threads to perform tasks."""

    def __init__(self, workers: int) -> None:
        """Create a :class:`.Queue`."""
        self.tasks: Queue = Queue(workers)
        for _ in range(workers):
            Worker(self.tasks)

    def map(self, func: Callable, args_list: List[Tuple]) -> None:
        """Apply ``func`` to each of the elements of ``args_list``."""
        for args in args_list:
            self.tasks.put((func, (args,)))

    def await_completion(self) -> None:
        """Await completion of all the tasks in the queue."""
        self.tasks.join()


class AsynchronousCheckingStrategy(BaseCheckingStrategy):
    """Runs checks in parallel processes."""

    def check(self, workspace: 'Workspace',
              *checkers: IChecker) -> None:
        """Run checks in parallel threads."""
        pool = ThreadPool(10)
        while workspace.has_unchecked_files:
            pool.map(partial(self._check_file, workspace, checkers), [(u_file,) for u_file in workspace.iter_files(allow_directories=True)])
            pool.await_completion()

            # Perform workspace-wide checks.
            for checker in checkers:
                if hasattr(checker, 'check_workspace'):
                    checker.check_workspace(workspace)

    def _check_file(self, workspace: 'Workspace',
                    checkers: Iterable[IChecker],
                    u_file: UserFile) -> None:
        for checker in checkers:
            try:
                u_file = checker(workspace, u_file)
            except StopCheck as e:
                logger.debug('Got StopCheck from %s on %s: %s',
                                checker.__class__.__name__, u_file.path,
                                str(e))
            if u_file.is_removed:   # If a checker removes a file, no
                break               # further action should be taken.

        u_file.is_checked = True



class SynchronousCheckingStrategy:
    """Runs checks one file at a time."""

    def check(self, workspace: 'Workspace',
              *checkers: IChecker) -> None:
        """Run checks one file at a time."""
        # This may take a few passes, as we may be unpacking compressed files.
        while workspace.has_unchecked_files:
            for u_file in workspace.iter_files(allow_directories=True):
                if u_file.is_checked:   # Don't run checks twice on the same
                    continue            # file.
                for checker in checkers:
                    try:
                        u_file = checker(workspace, u_file)
                    except StopCheck as e:
                        logger.debug('Got StopCheck from %s on %s: %s',
                                     checker.__class__.__name__, u_file.path,
                                     str(e))
                    if u_file.is_removed:   # If a checker removes a file, no
                        break               # further action should be taken.
                u_file.is_checked = True

            # Perform workspace-wide checks.
            for checker in checkers:
                if hasattr(checker, 'check_workspace'):
                    checker.check_workspace(workspace)


def create_strategy(app: Flask) -> ICheckingStrategy:
    return SynchronousCheckingStrategy()
    # return AsynchronousCheckingStrategy()
