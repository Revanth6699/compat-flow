from app.services.batch_processing import (
    BatchConfigurationError,
    DiskBackedDuplicateTracker,
    iter_batches,
)


def test_iter_batches_is_lazy_and_preserves_every_item():
    visited = []

    def source():
        for value in range(7):
            visited.append(value)
            yield value

    batches = iter_batches(source(), batch_size=3)
    assert next(batches) == [0, 1, 2]
    assert visited == [0, 1, 2]
    assert list(batches) == [[3, 4, 5], [6]]
    assert visited == list(range(7))


def test_iter_batches_rejects_unsafe_batch_sizes():
    for size in (0, -1, 10_001, True):
        try:
            list(iter_batches([], size))
        except BatchConfigurationError:
            pass
        else:
            raise AssertionError(f"batch size {size!r} should be rejected")


def test_disk_backed_duplicates_are_detected_across_batches_and_cleaned_up():
    with DiskBackedDuplicateTracker() as tracker:
        first = tracker.check_and_add(("sku", "001"), "row:2")
        second = tracker.check_and_add(("sku", "002"), "row:3")
        duplicate = tracker.check_and_add(("sku", "001"), "row:502")
        path = tracker.path
        assert not first.duplicate
        assert not second.duplicate
        assert duplicate.duplicate
        assert duplicate.first_source_location == "row:2"
    assert not path.exists()


def test_duplicate_tracker_rejects_use_after_close():
    tracker = DiskBackedDuplicateTracker()
    tracker.close()
    try:
        tracker.check_and_add(("sku", "001"), "row:2")
    except RuntimeError:
        pass
    else:
        raise AssertionError("closed tracker must reject writes")
