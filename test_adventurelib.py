import copy
import functools
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from unittest.mock import patch

import pytest

import adventurelib
from adventurelib import (
    Bag,
    InvalidCommand,
    Item,
    Pattern,
    Room,
    _handle_command,
    say,
    when,
)


@contextmanager
def active_context(ctx):
    """Context manager to set the current command context."""
    prev_ctx = adventurelib.current_context
    adventurelib.set_context(ctx)
    try:
        yield
    finally:
        adventurelib.set_context(prev_ctx)


@pytest.fixture(autouse=True)
def setup_commands():
    orig_commands = adventurelib.commands[:]
    yield
    adventurelib.commands[:] = orig_commands


@pytest.fixture(autouse=True)
def setup_room():
    original_room = {}
    for key, value in Room.__dict__.items():
        if not key.startswith("__"):
            try:
                original_room[key] = copy.copy(value)
            except TypeError:
                original_room[key] = value
    yield
    for key in list(Room.__dict__.keys()):
        if not key.startswith("__") and key not in original_room:
            delattr(Room, key)
    for key, value in original_room.items():
        try:
            setattr(Room, key, value)
        except AttributeError:
            pass


def test_match():
    matches = Pattern("apple").match(["apple"])
    assert matches == {}


def test_no_match_different_words():
    matches = Pattern("look").match(["apple"])
    assert matches is None


def test_no_match_extra_words():
    matches = Pattern("look").match(["look", "at", "butler"])
    assert matches is None


def test_multiple_words():
    pat = Pattern("take apple")
    matches = pat.match(["take", "apple"])
    assert matches == {}


def test_multiple_words_mismatch():
    matches = Pattern("take apple").match(["take", "tortoise"])
    assert matches is None


def test_multiple_words_mismatch_length():
    matches = Pattern("take apple").match(["take", "golden", "apple"])
    assert matches is None


def test_capturing_match():
    matches = Pattern("take ITEM").match(["take", "apple"])
    assert matches == {"item": "apple"}


def test_multiple_captures():
    pat = Pattern("give ITEM to PERSON")
    matches = pat.match(["give", "apple", "to", "wizard"])
    assert matches == {"item": "apple", "person": "wizard"}


def test_capturing_multiword():
    matches = Pattern("take ITEM").match(["take", "golden", "apple"])
    assert matches == {"item": "golden apple"}


def test_multiple_multiword_captures():
    pat = Pattern("give ITEM to PERSON")
    matches = pat.match(["give", "golden", "apple", "to", "evil", "wizard"])
    assert matches == {"item": "golden apple", "person": "evil wizard"}


def test_word_combinations():
    combos = Pattern.word_combinations(have=3, placeholders=2)
    assert list(combos) == [(2, 1), (1, 2)]


def test_word_combinations_2():
    combos = Pattern.word_combinations(have=4, placeholders=2)
    assert list(combos) == [(3, 1), (2, 2), (1, 3)]


def test_word_combinations_3():
    combos = Pattern.word_combinations(have=4, placeholders=3)
    assert list(combos) == [(2, 1, 1), (1, 2, 1), (1, 1, 2)]


def test_word_combinations_4():
    combos = Pattern.word_combinations(have=5, placeholders=3)
    assert list(combos) == [
        (3, 1, 1),
        (2, 2, 1),
        (2, 1, 2),
        (1, 3, 1),
        (1, 2, 2),
        (1, 1, 3),
    ]


def test_register():
    called = False

    @when("north")
    def func():
        nonlocal called
        called = True

    print(adventurelib.commands)
    _handle_command("north")
    assert called is True


def test_register_args():
    args = None

    @when("north", dir="north")
    def func(dir):
        nonlocal args
        args = [dir]

    _handle_command("north")
    assert args == ["north"]


@pytest.mark.parametrize(
    "ctx,expected",
    [
        (None, "north"),
        ("confused", "south"),
        ("confused.really", "cauliflower"),
    ],
)
def test_register_context(ctx, expected):
    """The result of a command changes in different contexts."""
    cmd = None

    # Register out of order to test tie-breaking by context nesting depth
    @when("north", dir="north")
    @when("north", dir="cauliflower", context="confused.really")
    @when("north", dir="south", context="confused")
    def func(dir):
        nonlocal cmd
        cmd = dir

    with active_context(ctx):
        _handle_command("north")
    assert cmd == expected


def test_register_match():
    args = None

    @when("hit TARGET with WEAPON", verb="hit")
    def func(target, weapon, verb):
        nonlocal args
        args = [target, weapon, verb]

    _handle_command("hit dragon with glass sword")
    assert args == ["dragon", "glass sword", "hit"]


def say_at_width(width, msg):
    buf = StringIO()
    with patch("adventurelib.get_terminal_size", return_value=(width, 24)):
        with redirect_stdout(buf):
            say(msg)
    return buf.getvalue()


def test_say_room():
    """say() will format input as strings."""
    r = Room("You are standing in a hallway.")

    buf = StringIO()
    with redirect_stdout(buf):
        say(r)
    assert buf.getvalue() == "You are standing in a hallway.\n"


def test_say_wrap():
    """The say() function will print output wrapped to the terminal width."""
    out = say_at_width(
        40,
        """
    This is a long sentence that the say command will wrap.
    """,
    )

    assert out == ("This is a long sentence that the say\n" "command will wrap.\n")


def test_say_wrap2():
    """The say() function will print output wrapped to the terminal width."""
    out = say_at_width(
        20,
        """
    This is a long sentence that the say command will wrap.
    """,
    )

    assert out == (
        "This is a long\n" "sentence that the\n" "say command will\n" "wrap.\n"
    )


def test_say_multiple_paragraph():
    """Paragraphs separated by a blank line will be wrapped separately."""
    out = say_at_width(
        40,
        """
    This is a long sentence that the say command will wrap.

    And this is a second paragraph that is separately wrapped.
    """,
    )

    assert out == (
        "This is a long sentence that the say\n"
        "command will wrap.\n"
        "\n"
        "And this is a second paragraph that is\n"
        "separately wrapped.\n"
    )


def test_say_multiline_paragraph():
    """We can wrap a sentence written in multiple input lines."""
    out = say_at_width(
        40,
        """
    This is a long sentence that the say command will wrap,
    and this clause is indented to match.
    """,
    )

    assert out == (
        "This is a long sentence that the say\n"
        "command will wrap, and this clause is\n"
        "indented to match.\n"
    )


@patch("random.randrange", return_value=0)
def test_bag_get_random(randrange):
    """We can select an item from a bag at random."""
    bag = Bag(map(Item, "abc"))
    assert bag.get_random() == list(bag)[0]
    randrange.assert_called_once_with(3)


@patch("random.randrange", return_value=1)
def test_bag_get_random2(randrange):
    """We can select an item from a bag at random."""
    bag = Bag(map(Item, "abc"))
    assert bag.get_random() == list(bag)[1]
    randrange.assert_called_once_with(3)


def test_empty_bag_get_random():
    """Choosing from an empty bag returns None."""
    bag = Bag()
    assert bag.get_random() is None


@patch("random.randrange", return_value=0)
def test_bag_take_random(randrange):
    """We can select and remove an item from a bag at random."""
    bag = Bag(map(Item, "abc"))
    items = list(bag)
    assert bag.take_random() == items[0]
    assert bag == Bag(items[1:])
    randrange.assert_called_once_with(3)


def test_bag_find():
    """We can find items in a bag by name, case insensitively."""
    name, *aliases = ["Name", "UPPER ALIAS", "lower alias"]
    named_item = Item(name, *aliases)
    appellative_item = Item("appellation", *aliases)
    nameless_item = Item("noname", "none at all")
    bag = Bag({named_item, appellative_item, nameless_item})

    assert bag.find("name") is named_item
    assert bag.find("Name") is named_item
    assert bag.find("NAME") is named_item
    assert bag.find("appellation") is appellative_item
    assert bag.find("upper alias") in {named_item, appellative_item}
    assert bag.find("LOWER ALIAS") in {named_item, appellative_item}
    assert not bag.find("other")


@pytest.mark.parametrize("current_context", ["foo", "foo.bar", "foo.bar.baz"])
def test_match_context(current_context):
    """We can match contexts."""
    assert adventurelib._match_context("foo", current_context)


@pytest.mark.parametrize(
    "current_context",
    [None, "bar", "bar.foo"],
)
def test_no_match_context(current_context):
    """A context doesn't match if it is not "within" the pattern context."""
    assert not adventurelib._match_context("foo", current_context)


def test_match_context_none():
    """The current context matches if the pattern context is None."""
    assert adventurelib._match_context(None, "foo.bar")


@pytest.mark.parametrize("context", [None, "foo", "foo.bar"])
def test_validate_context(context):
    """We can validate valid contexts."""
    adventurelib._validate_context(context)


def test_validate_context_empty():
    """An empty string is not a valid context."""
    with pytest.raises(ValueError) as exc:
        adventurelib._validate_context("")
    assert str(exc.value) == "Context '' may not be empty"


def test_validate_context_start_dot():
    """A context that starts with . is invalid."""
    with pytest.raises(ValueError) as exc:
        adventurelib._validate_context(".foo")
    assert str(exc.value) == "Context '.foo' may not start with ."


def test_validate_context_end_dot():
    """A context that ends with . is invalid."""
    with pytest.raises(ValueError) as exc:
        adventurelib._validate_context("foo.bar.")
    assert str(exc.value) == "Context 'foo.bar.' may not end with ."


def test_validate_context_double_dot():
    """A context that contains .. is invalid."""
    with pytest.raises(ValueError) as exc:
        adventurelib._validate_context("foo..bar")
    assert str(exc.value) == "Context 'foo..bar' may not contain .."


def test_validate_context_wrong():
    """A context that is wrong in various ways has a custom message."""
    with pytest.raises(ValueError) as exc:
        adventurelib._validate_context(".foo.bar.")
    err = str(exc.value)
    assert err == "Context '.foo.bar.' may not start with . or end with ."


def test_validate_pattern_double_ident():
    """A pattern with identifier used twice is incorrect"""
    with pytest.raises(adventurelib.InvalidCommand) as exc:
        Pattern("take I with I")
    err = str(exc.value)
    assert err == "Invalid command 'take I with I'" " Identifiers may only be used once"


def test_room_add_direction_not_lowercase():
    """Directions must be lowercase."""
    room = Room("Test Room")
    with pytest.raises(
        InvalidCommand,
        match="Invalid direction 'Up': directions must be all lowercase.",
    ):
        room.add_direction("Up", "down")


def test_room_add_direction_already_added():
    """Directions must be unique."""
    room = Room("Test Room")
    room.add_direction("up", "down")
    with pytest.raises(
        KeyError,
        match="'up' is already a direction!",
    ):
        room.add_direction("up", "down")


def test_room_add_direction_is_attribute():
    """Directions must not be named as existing attributes."""
    room = Room("Test Room")
    with pytest.raises(
        AttributeError,
        match="'exit' is an existing attribute and cannot be used as direction name!",
    ):
        room.add_direction("up", "exit")


def passthrough_decorator(func):
    """A decorator that accepts arbitrary args, without functools.wraps."""

    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def _commands_state():
    """Extract a comparable, deep-copyable snapshot of registered commands."""
    return copy.deepcopy(
        [
            (p.orig_pattern, p.pattern_context, list(p.argnames), func, dict(kw))
            for p, func, kw in adventurelib.commands
        ]
    )


def _run_command(cmd):
    """Handle a command, swallowing the printed output."""
    with redirect_stdout(StringIO()):
        _handle_command(cmd)


def test_register_wrapped_command():
    """A command wrapped by a *args/**kwargs decorator still registers."""
    called = []

    @when("look")
    @passthrough_decorator
    def look():
        called.append("look")

    _run_command("look")
    assert called == ["look"]


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("take apple", "apple"),
        ("take golden apple", "golden apple"),
        ("take the one ring", "the one ring"),
    ],
)
def test_register_wrapped_command_args(typed, expected):
    """Captured placeholder args pass through the wrapper unchanged."""
    got = []

    @when("take ITEM")
    @passthrough_decorator
    def take(item):
        got.append(item)

    _run_command(typed)
    assert got == [expected]


def test_register_wrapped_command_with_kwargs():
    """Fixed keyword args pass through the wrapper alongside captures."""
    got = []

    @when("hit TARGET with WEAPON", verb="hit")
    @passthrough_decorator
    def hit(target, weapon, verb):
        got.append((target, weapon, verb))

    _run_command("hit dragon with glass sword")
    assert got == [("dragon", "glass sword", "hit")]


def test_register_wrapped_command_functools_wraps():
    """A decorator using functools.wraps registers and dispatches."""
    calls = []

    def tracing(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            calls.append("traced")
            return func(*args, **kwargs)

        return inner

    @when("wave")
    @tracing
    def wave():
        calls.append("waved")

    _run_command("wave")
    assert calls == ["traced", "waved"]


def test_register_decorator_order_when_innermost():
    """@when applied under a decorator registers the original function."""
    calls = []

    def tracing(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            calls.append("traced")
            return func(*args, **kwargs)

        return inner

    @tracing
    @when("jump")
    def jump():
        calls.append("jumped")

    _run_command("jump")
    assert calls == ["jumped"]


@pytest.mark.parametrize(
    "func",
    [
        lambda: None,  # missing the captured argument
        lambda wrong: None,  # wrong argument name
        lambda item, extra: None,  # extra argument without a default
        lambda *args: None,  # cannot accept the captured keyword argument
    ],
    ids=["missing-arg", "wrong-name", "extra-required", "varargs-only"],
)
def test_register_incompatible_signature_rejected(func):
    """Signatures that cannot bind the captured args are still rejected."""
    before = _commands_state()
    with pytest.raises(InvalidCommand):
        when("take ITEM")(func)
    assert _commands_state() == before


@pytest.mark.parametrize(
    "func",
    [
        lambda item, extra=None: None,  # extra argument with a default
        lambda *args, **kwargs: None,  # generic wrapper signature
        lambda **kwargs: None,  # keyword-only catch-all
    ],
    ids=["extra-default", "args-kwargs", "kwargs-only"],
)
def test_register_compatible_signature_accepted(func):
    """Signatures that can bind the captured args register successfully."""
    before = _commands_state()
    when("take ITEM")(func)
    after = _commands_state()
    assert len(after) == len(before) + 1
    assert after[:-1] == before


def test_register_failure_then_success():
    """A rejected registration leaves later registrations unaffected."""
    before = _commands_state()
    with pytest.raises(InvalidCommand):
        when("take ITEM")(lambda wrong: None)
    assert _commands_state() == before

    got = []

    @when("take ITEM")
    @passthrough_decorator
    def take(item):
        got.append(item)

    _run_command("take apple")
    assert got == ["apple"]


def test_wrapped_command_multiple_rounds():
    """A wrapped command can be dispatched repeatedly and deterministically."""
    got = []

    @when("take ITEM")
    @passthrough_decorator
    def take(item):
        got.append(item)

    for _ in range(3):
        _run_command("take apple")
        _run_command("take golden apple")
    assert got == ["apple", "golden apple"] * 3


def test_wrapped_command_replay_deterministic():
    """The same input sequence produces the same results when replayed."""

    def play():
        got = []

        @when("take ITEM")
        @passthrough_decorator
        def take(item):
            got.append(item)

        for typed in ["take apple", "take golden apple", "take apple"]:
            _run_command(typed)
        adventurelib.commands.pop()
        return got

    first = play()
    second = play()
    assert first == second == ["apple", "golden apple", "apple"]


def test_wrapped_commands_out_of_order_registration():
    """Dispatch results do not depend on command registration order."""

    def play(order):
        got = []

        def make_take():
            @when("take ITEM")
            @passthrough_decorator
            def take(item):
                got.append(("take", item))

        def make_drop():
            @when("drop ITEM")
            @passthrough_decorator
            def drop(item):
                got.append(("drop", item))

        makers = {"take": make_take, "drop": make_drop}
        for name in order:
            makers[name]()
        _run_command("take apple")
        _run_command("drop apple")
        adventurelib.commands.pop()
        adventurelib.commands.pop()
        return got

    assert play(["take", "drop"]) == play(["drop", "take"]) == [
        ("take", "apple"),
        ("drop", "apple"),
    ]


def test_wrapped_command_partial_match_unknown():
    """Unknown input still falls through after a wrapped command matches."""
    got = []

    @when("take ITEM")
    @passthrough_decorator
    def take(item):
        got.append(item)

    buf = StringIO()
    with redirect_stdout(buf):
        _handle_command("take apple")
        _handle_command("frobnicate apple")
        _handle_command("take")
    out = buf.getvalue()
    assert got == ["apple"]
    assert "I don't understand 'frobnicate apple'." in out
    assert "I don't understand 'take'." in out


def test_wrapped_command_with_context():
    """Wrapped commands respect contexts like unwrapped commands."""
    got = []

    @when("look", context="confused")
    @passthrough_decorator
    def look_confused():
        got.append("confused")

    @when("look")
    @passthrough_decorator
    def look():
        got.append("normal")

    _run_command("look")
    with active_context("confused"):
        _run_command("look")
    _run_command("look")
    assert got == ["normal", "confused", "normal"]
