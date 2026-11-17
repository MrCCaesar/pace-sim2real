# SPDX-License-Identifier: Apache-2.0

"""Private, process-isolated observation for the native collector."""

from __future__ import annotations

import importlib
import multiprocessing as mp
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

STARTUP_TIMEOUT = 10.0
SHUTDOWN_TIMEOUT = 2.0
TERMINATE_TIMEOUT = 1.0
KILL_TIMEOUT = 1.0
DISPLAY_PERIOD = 1.0 / 30.0


def _viewer_process(path: str, state_buffer: Any, lock: Any, changed: Any, stop: Any, events: Any) -> None:
    """Only this process imports the GUI; it never owns collection state."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    viewer = None
    render_threads: set[threading.Thread] = set()
    try:
        # Native MuJoCo and multiprocessing shared-memory primitives have dynamic APIs.
        mj: Any = importlib.import_module("mujoco")
        gui: Any = importlib.import_module("mujoco.viewer")
        model = mj.MjModel.from_xml_path(path)
        data = mj.MjData(model)
        state = np.frombuffer(state_buffer, dtype=np.float64)
        with lock:
            mj.mj_setState(model, data, state.copy(), mj.mjtState.mjSTATE_INTEGRATION)
        mj.mj_forward(model, data)
        existing_threads = set(threading.enumerate())
        viewer = gui.launch_passive(model, data, show_left_ui=False, show_right_ui=False)
        render_threads = set(threading.enumerate()) - existing_threads
        viewer.sync()
        events.send(("ready", ""))
        while not stop.value:
            if not viewer.is_running():
                events.send(("closed", ""))
                return
            snapshot = None
            if lock.acquire(False):
                try:
                    if changed.value:
                        snapshot = state.copy()
                        changed.value = False
                finally:
                    lock.release()
            if snapshot is not None:
                mj.mj_setState(model, data, snapshot, mj.mjtState.mjSTATE_INTEGRATION)
                mj.mj_forward(model, data)
                viewer.sync()
            time.sleep(0.01)
        events.send(("stopped", ""))
    except BaseException as exc:
        events.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        if viewer is not None:
            viewer.close()
        # close() only requests exit. Finish renderer teardown before Python/GLFW atexit.
        # The parent enforces the bounded shutdown deadline if a renderer stalls.
        for thread in render_threads:
            thread.join()
        events.close()


class ViewerSession:
    """Run-scoped viewer lifecycle; private to the collection scripts."""

    def __init__(self, path: Path, model: Any, data: Any):
        self._mj: Any = importlib.import_module("mujoco")
        self._model = model
        self._kind = self._mj.mjtState.mjSTATE_INTEGRATION
        ctx = mp.get_context("spawn")
        self._buffer = ctx.RawArray("d", self._mj.mj_stateSize(model, self._kind))
        self._state = np.frombuffer(self._buffer, dtype=np.float64)
        self._mj.mj_getState(model, data, self._state, self._kind)
        self._lock = ctx.Lock()
        # No Event/Queue locks: a child dying while holding one could strand the parent.
        self._changed = ctx.RawValue("b", False)  # protected by the snapshot lock
        self._stop = ctx.RawValue("b", False)  # one writer, a one-byte stop flag
        self._events, self._sender = ctx.Pipe(duplex=False)
        self._process = ctx.Process(
            target=_viewer_process,
            args=(str(path), self._buffer, self._lock, self._changed, self._stop, self._sender),
            name="mujoco-observer",
        )
        self._ready = False
        self._closed = False
        self._stopped = False
        self._eof = False
        self._started = False
        self._origin = 0.0
        self._simulation_origin = float(data.time)
        self._next_frame = 0.0

    def __enter__(self) -> ViewerSession:
        try:
            deadline = time.monotonic() + STARTUP_TIMEOUT
            self._process.start()
            self._started = True
            self._sender.close()
            while not self._ready:
                self._poll()
                if self._closed and not self._ready:
                    raise RuntimeError("Viewer closed before startup completed")
                if time.monotonic() >= deadline:
                    raise RuntimeError("Viewer startup timed out")
                self._events.poll(min(0.01, max(0.0, deadline - time.monotonic())))
            self._origin = time.monotonic()
            self._next_frame = self._origin + DISPLAY_PERIOD
            return self
        except BaseException as exc:
            self.__exit__(type(exc), exc, exc.__traceback__)
            raise

    def _drain(self) -> None:
        while not self._eof and self._events.poll():
            try:
                event, detail = self._events.recv()
            except EOFError:
                self._eof = True
                break
            if event == "error":
                raise RuntimeError(f"Viewer failed: {detail}")
            if event == "ready":
                self._ready = True
            elif event == "closed":
                self._closed = True
            elif event == "stopped":
                self._stopped = True

            else:
                raise RuntimeError(f"Viewer sent an invalid lifecycle event: {event}")

    def _poll(self) -> None:
        self._drain()
        code = self._process.exitcode
        if code is not None:
            # Exit may become visible just after the first drain.
            self._drain()
            if code != 0 or not self._closed:
                raise RuntimeError(f"Viewer exited unexpectedly (code {code})")
        if self._stopped or (self._eof and not self._closed):
            raise RuntimeError("Viewer disconnected unexpectedly")

    def update(self, data: Any) -> None:
        """Observe lifecycle, pace physics, and publish at most one latest state."""
        self._poll()
        while not self._closed:
            remaining = self._origin + float(data.time) - self._simulation_origin - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(remaining, 0.01))
            self._poll()
        now = time.monotonic()
        if not self._closed and now >= self._next_frame:
            # Never wait on a display lock or queue; a busy reader costs only a frame.
            if self._lock.acquire(False):
                try:
                    self._mj.mj_getState(self._model, data, self._state, self._kind)
                    self._changed.value = True
                finally:
                    self._lock.release()
            self._next_frame = now + DISPLAY_PERIOD

    def _shutdown(self) -> None:
        if not self._started:
            return
        self._stop.value = True
        self._process.join(SHUTDOWN_TIMEOUT)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(TERMINATE_TIMEOUT)
        if self._process.is_alive():
            self._process.kill()
            self._process.join(KILL_TIMEOUT)
        if self._process.is_alive():
            raise RuntimeError("Viewer cleanup failed: child still running after kill")

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        # Defer SIGINT through every escalation wait, then preserve cancellation.
        # Ignoring SIGINT would incorrectly save a completed run after the user cancels.
        interrupted = False
        previous = None

        def defer_interrupt(signum: int, frame: Any) -> None:
            nonlocal interrupted
            interrupted = True

        if threading.current_thread() is threading.main_thread():
            previous = signal.signal(signal.SIGINT, defer_interrupt)
        try:
            self._finish(exc)
        except BaseException as error:
            if not interrupted:
                raise
            print(f"Viewer cleanup during cancellation: {error}", file=sys.stderr)
        finally:
            if previous is not None:
                signal.signal(signal.SIGINT, previous)
        if interrupted:
            raise KeyboardInterrupt

    def _finish(self, exc: Any) -> None:
        failure = None
        try:
            if self._started:
                self._poll()
        except BaseException as error:
            failure = error
        try:
            self._shutdown()
            if self._started:
                self._drain()
                if self._process.exitcode != 0:
                    raise RuntimeError(f"Viewer cleanup failed (exit code {self._process.exitcode})")
                if not (self._closed or self._stopped):
                    raise RuntimeError("Viewer exited without acknowledging shutdown")
        except BaseException as error:
            failure = error
        finally:
            self._events.close()
            self._sender.close()
            if self._started and not self._process.is_alive():
                self._process.close()
            # Tracebacks may retain this session; release IPC now, not at cyclic GC.
            del self._lock, self._state, self._buffer, self._changed, self._stop
        if failure is not None:
            if exc is None:
                raise failure
            exc.add_note(f"Viewer cleanup: {failure}")
            print(f"Viewer cleanup: {failure}", file=sys.stderr)
