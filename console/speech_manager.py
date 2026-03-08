from __future__ import annotations

import subprocess
import threading
from collections import deque
from collections.abc import Callable


class SpeechInterrupted(RuntimeError):
    """Raised when active speech is interrupted by a local stop request."""


class SpeechManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: deque[tuple[int, str, Callable[[int], None]]] = deque()
        self._active_processes: set[subprocess.Popen] = set()
        self._speaking = False
        self._generation = 0
        self._worker_started = False
        self._has_work = threading.Condition(self._lock)

    def start_speech(self, runner: Callable[[int], None], label: str = "speech") -> None:
        with self._lock:
            generation = self._generation
            self._queue.append((generation, label, runner))
            if not self._worker_started:
                thread = threading.Thread(target=self._run_worker, name="jarvis-speech-worker", daemon=True)
                thread.start()
                self._worker_started = True
            self._has_work.notify()
        print(f"[SpeechManager] queued label={label} generation={generation}")

    def stop_speech(self) -> dict[str, int]:
        with self._lock:
            self._generation += 1
            dropped = len(self._queue)
            self._queue.clear()
            processes = list(self._active_processes)
            self._active_processes.clear()
            was_speaking = self._speaking
            generation = self._generation

        print(
            f"[SpeechManager] stop-triggered generation={generation} "
            f"active_processes={len(processes)} dropped_queue={dropped} was_speaking={int(was_speaking)}"
        )
        terminated = 0
        for proc in processes:
            if self._terminate_process(proc):
                terminated += 1

        print(
            f"[SpeechManager] stop-complete generation={generation} "
            f"terminated={terminated} dropped_queue={dropped}"
        )
        return {"terminated": terminated, "dropped_queue": dropped}

    def is_speaking(self) -> bool:
        with self._lock:
            return self._speaking or bool(self._active_processes)

    def register_process(self, proc: subprocess.Popen, generation: int) -> None:
        with self._lock:
            if generation != self._generation:
                raise SpeechInterrupted("Speech request was cancelled before playback started")
            self._active_processes.add(proc)

    def unregister_process(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._active_processes.discard(proc)

    def assert_not_interrupted(self, generation: int) -> None:
        with self._lock:
            if generation != self._generation:
                raise SpeechInterrupted("Speech request interrupted")

    def _run_worker(self) -> None:
        while True:
            with self._lock:
                while not self._queue:
                    self._has_work.wait()
                generation, label, runner = self._queue.popleft()
                if generation != self._generation:
                    continue
                self._speaking = True

            print(f"[SpeechManager] start label={label} generation={generation}")
            try:
                runner(generation)
                print(f"[SpeechManager] completed label={label} generation={generation}")
            except SpeechInterrupted:
                print(f"[SpeechManager] interrupted label={label} generation={generation}")
            except Exception as exc:
                print(f"[SpeechManager] failed label={label} generation={generation} error={exc}")
            finally:
                with self._lock:
                    if not self._active_processes:
                        self._speaking = False

    @staticmethod
    def _terminate_process(proc: subprocess.Popen) -> bool:
        if proc.poll() is not None:
            return False
        try:
            proc.terminate()
            try:
                proc.wait(timeout=0.15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=0.15)
            return True
        except Exception:
            return False


_speech_manager = SpeechManager()


def get_speech_manager() -> SpeechManager:
    return _speech_manager


def start_speech(runner: Callable[[int], None], label: str = "speech") -> None:
    _speech_manager.start_speech(runner=runner, label=label)


def stop_speech() -> dict[str, int]:
    return _speech_manager.stop_speech()


def is_speaking() -> bool:
    return _speech_manager.is_speaking()
