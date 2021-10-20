from stiltctl.events import Event
from stiltctl.exceptions import NotFound
from stiltctl.unit_of_work import UnitOfWork


class FakeEvent(Event):
    value: int


def test_insert_retrieve_event(uow: UnitOfWork):
    expected = FakeEvent(value=1)
    with uow:
        uow.events.add(expected)
    with uow:
        assert uow.events.get_event_count(FakeEvent) == 1

    with uow:
        event = uow.events.dequeue(FakeEvent)
        assert event == expected

    with uow:
        assert uow.events.get_event_count(FakeEvent) == 0


def test_insert_retrieve_multiple_events(uow: UnitOfWork):
    expected = [FakeEvent(value=2), FakeEvent(value=3)]
    with uow:
        uow.events.add_many(expected)
    with uow:
        assert uow.events.get_event_count(FakeEvent) == 2

    with uow:
        event = uow.events.dequeue(FakeEvent)
        assert event == expected[0]
        event = uow.events.dequeue(FakeEvent)
        assert event == expected[1]

    with uow:
        assert uow.events.get_event_count(FakeEvent) == 0


def test_subscription(uow: UnitOfWork):
    expected = [FakeEvent(value=4), FakeEvent(value=5)]
    with uow:
        uow.events.add_many(expected)

    count = 0
    while True:
        with uow:
            try:
                event = uow.events.dequeue(FakeEvent)
            except NotFound:
                break
            assert event == expected[count]
            count += 1

    assert count == len(expected)
    with uow:
        assert uow.events.get_event_count(FakeEvent) == 0
