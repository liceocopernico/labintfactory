import threading
import time

import pytest

from labdaemon.core.worker import BoardWorker, DeviceProxy


@pytest.fixture
def worker():
    w = BoardWorker("test")
    w.start()
    yield w
    w.shutdown()


def test_jobs_run_in_order_on_the_worker(worker):
    order = []
    futures = [worker.submit(lambda i=i: order.append((i, threading.current_thread().name))) for i in range(5)]
    for f in futures:
        f.result(1)
    assert [i for i, _ in order] == list(range(5))
    assert all(name == "board-test" for _, name in order)


def test_urgent_jobs_jump_the_queue(worker):
    gate = threading.Event()
    order = []
    worker.submit(gate.wait, 2)
    normal = worker.submit(order.append, "normal")
    urgent = worker.submit(order.append, "stop", urgent=True)
    gate.set()
    normal.result(1), urgent.result(1)
    assert order == ["stop", "normal"]


def test_call_propagates_results_and_errors(worker):
    assert worker.call(lambda: 42, timeout=1) == 42
    with pytest.raises(ZeroDivisionError):
        worker.call(lambda: 1 / 0, timeout=1)
    # calling from inside the worker runs inline instead of deadlocking
    assert worker.call(lambda: worker.call(lambda: "inner"), timeout=1) == "inner"


def test_polling_and_poll_failures(worker):
    got, failed = [], []
    worker.polled.connect(lambda key, value, t: got.append((key, value)))
    worker.poll_failed.connect(lambda key, exc: failed.append(key))
    counter = iter(range(100))
    worker.add_poll("a", lambda: next(counter), 0.05)
    worker.add_poll("b", lambda: 1 / 0, 0.05)
    time.sleep(0.3)
    worker.remove_poll("a")
    worker.remove_poll("b")
    assert len(got) >= 3 and got[0] == ("a", 0)
    assert failed and set(failed) == {"b"}


def test_shutdown_refuses_new_jobs():
    w = BoardWorker("x")
    w.start()
    w.shutdown()
    with pytest.raises(RuntimeError):
        w.submit(lambda: 1).result(1)


def test_proxy_runs_methods_on_the_worker(worker):
    class Thing:
        display_name = "thing"
        value = 3

        def where(self):
            return threading.current_thread().name

    p = DeviceProxy(worker, Thing())
    assert p.where() == "board-test"
    assert p.value == 3
    with pytest.raises(AttributeError):
        p.value = 4
