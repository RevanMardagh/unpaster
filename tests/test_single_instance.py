from unpaster import main

NAME = "unpaster-test-mutex-9f3a"


def test_first_acquire_succeeds():
    handle = main.acquire_single_instance(NAME)
    assert handle is not None
    main.release_single_instance(handle)


def test_second_acquire_while_held_fails():
    first = main.acquire_single_instance(NAME)
    try:
        assert main.acquire_single_instance(NAME) is None
    finally:
        main.release_single_instance(first)


def test_acquire_succeeds_again_after_release():
    first = main.acquire_single_instance(NAME)
    main.release_single_instance(first)
    second = main.acquire_single_instance(NAME)
    assert second is not None
    main.release_single_instance(second)
