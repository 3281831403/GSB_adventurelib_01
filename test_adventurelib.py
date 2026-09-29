import copy
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


def _bag_snapshot(bag):
    """Take a deep-copy snapshot of a bag's externally visible state."""
    return copy.deepcopy(
        {
            "items": sorted(item.aliases for item in bag),
            "alias_map": {
                alias: sorted(item.aliases for item in items)
                for alias, items in bag._alias_dict.items()
            },
        }
    )


def test_bag_find_by_item_object():
    """find() accepts an Item and matches it by identity."""
    lamp = Item("brass lamp", "lamp")
    key = Item("rusty key", "key")
    bag = Bag({lamp, key})

    assert bag.find(lamp) is lamp
    assert bag.find(key) is key
    # find() must not remove anything
    assert _bag_snapshot(bag) == _bag_snapshot(Bag({lamp, key}))


def test_bag_find_by_item_object_not_present():
    """find() with an Item that is not in the bag returns None."""
    bag = Bag({Item("lamp")})
    before = _bag_snapshot(bag)

    assert bag.find(Item("lamp")) is None
    assert _bag_snapshot(bag) == before


def test_bag_take_by_item_object():
    """take() accepts an Item object, removes it and returns it."""
    lamp = Item("brass lamp", "lamp")
    key = Item("rusty key", "key")
    bag = Bag({lamp, key})

    assert bag.take(lamp) is lamp
    assert lamp not in bag
    assert "lamp" not in bag
    assert bag == Bag({key})
    # The alias dict must not keep entries for removed items.
    assert set(bag._alias_dict) == {"rusty key", "key"}


def test_bag_find_by_name_then_take_by_object():
    """The reported bug: find by name, then take the found object."""
    lamp = Item("brass lamp", "lamp")
    bag = Bag({lamp, Item("rusty key", "key")})

    obj = bag.find("lamp")
    assert obj is lamp
    assert bag.take(obj) is lamp
    assert bag.find("lamp") is None


@pytest.mark.parametrize("bad_arg", [None, 42, 3.14, ["lamp"], ("lamp",)])
def test_bag_find_invalid_type(bad_arg):
    """find() raises a readable TypeError for non-str, non-Item arguments."""
    bag = Bag({Item("lamp")})
    before = _bag_snapshot(bag)

    with pytest.raises(TypeError, match="must be a str or Item"):
        bag.find(bad_arg)
    # A rejected call must leave the state field-for-field identical.
    assert _bag_snapshot(bag) == before


@pytest.mark.parametrize("bad_arg", [None, 42, 3.14, ["lamp"], ("lamp",)])
def test_bag_take_invalid_type(bad_arg):
    """take() raises a readable TypeError and rolls back fully."""
    lamp = Item("lamp")
    bag = Bag({lamp})
    before = _bag_snapshot(bag)

    with pytest.raises(TypeError, match="must be a str or Item"):
        bag.take(bad_arg)
    assert _bag_snapshot(bag) == before
    # A successful call right after the failure must be unaffected.
    assert bag.take(lamp) is lamp
    assert not bag


@pytest.mark.parametrize("missing", ["torch", "LAMP ", "", "lamp lamp"])
def test_bag_take_missing_name_returns_none(missing):
    """take() with a name that does not match returns None, then succeeds."""
    lamp = Item("lamp")
    bag = Bag({lamp})
    before = _bag_snapshot(bag)

    assert bag.take(missing) is None
    assert _bag_snapshot(bag) == before
    # Failure must not break a following successful call.
    assert bag.take("lamp") is lamp
    assert not bag


def test_bag_find_and_take_empty_bag():
    """Looking in an empty bag (resource exhaustion) returns None."""
    bag = Bag()

    assert bag.find("lamp") is None
    assert bag.find(Item("lamp")) is None
    assert bag.take("lamp") is None
    assert bag.take(Item("lamp")) is None
    assert _bag_snapshot(bag) == {"items": [], "alias_map": {}}


def test_bag_take_single_element_boundary():
    """A single-element bag empties exactly once."""
    lamp = Item("lamp")
    bag = Bag({lamp})

    assert bag.take(lamp) is lamp
    assert not bag
    assert bag._alias_dict == {}
    # Repeating the take on the now-empty bag keeps returning None.
    assert bag.take(lamp) is None
    assert bag.take("lamp") is None


def test_bag_take_repeated_calls_until_empty():
    """Repeated take() calls drain the bag one item per call."""
    items = [Item("coin", "coins") for _ in range(3)]
    bag = Bag(items)

    taken = [bag.take("coin") for _ in range(3)]
    assert sorted(taken, key=id) == sorted(items, key=id)
    assert not bag
    assert bag._alias_dict == {}
    # Further calls on the exhausted bag return None.
    assert bag.take("coin") is None


def test_bag_find_deterministic_with_shared_alias():
    """find() picks deterministically among items sharing an alias."""
    apple = Item("apple", "fruit")
    banana = Item("banana", "fruit")
    bag = Bag({banana, apple})

    # Repeated calls on the same bag return the identical object.
    first = bag.find("fruit")
    assert first is apple
    for _ in range(5):
        assert bag.find("fruit") is first

    # Replaying the same input sequence yields the same result.
    replay = Bag({Item("apple", "fruit"), Item("banana", "fruit")})
    assert replay.find("fruit").aliases == first.aliases

    # take() drains the shared alias in the same deterministic order.
    assert bag.take("fruit") is apple
    assert bag.take("fruit") is banana
    assert bag.take("fruit") is None


def test_bag_mixed_name_and_object_sequence():
    """Out-of-order mixes of names and objects behave per round."""
    lamp = Item("lamp")
    key = Item("key")
    coin = Item("coin")
    bag = Bag({lamp, key, coin})

    # Round 1: partial completion - a failed take between two good ones.
    assert bag.take("lamp") is lamp
    assert bag.take("torch") is None
    assert bag.take(key) is key
    assert bag == Bag({coin})

    # Round 2: retry after failure works, by object and by name.
    assert bag.take(coin) is coin
    assert not bag

    # Round 3: the empty bag stays stable under further calls.
    before = _bag_snapshot(bag)
    assert bag.take("coin") is None
    assert bag.take(lamp) is None
    assert _bag_snapshot(bag) == before


@pytest.mark.parametrize("query", ["lamp", "Lamp", "LAMP", "lAmP"])
def test_bag_take_by_name_case_insensitive(query):
    """take() by name is case-insensitive, like find()."""
    lamp = Item("Brass Lamp", "LAMP")
    bag = Bag({lamp})

    assert bag.take(query) is lamp
    assert not bag


def test_bag_contains_name_and_object():
    """The 'in' operator accepts both names and Item objects."""
    lamp = Item("lamp")
    bag = Bag({lamp})

    assert lamp in bag
    assert "lamp" in bag
    assert "LAMP" in bag
    assert Item("lamp") not in bag
    assert "torch" not in bag


def test_bag_copy_has_independent_alias_state():
    """copy() must not share alias sets with the original bag."""
    shared = Item("apple", "fruit")
    bag = Bag({shared, Item("banana", "fruit")})
    before = _bag_snapshot(bag)

    replica = bag.copy()
    assert _bag_snapshot(replica) == before

    # Mutating the copy must not leak into the original's lookup state.
    replica.add(Item("cherry", "fruit"))
    replica.take("banana")
    assert _bag_snapshot(bag) == before
    assert bag.find("fruit") in {shared, bag.find("banana")}

    # ... and vice versa.
    bag.add(Item("date", "fruit"))
    assert "date" not in replica


def test_bag_alias_dict_does_not_grow_unboundedly():
    """Adding and removing many items leaves no alias state behind."""
    bag = Bag()
    items = [Item("item%d" % i) for i in range(100)]
    for item in items:
        bag.add(item)
    assert len(bag._alias_dict) == 100

    for item in items:
        assert bag.take(item) is item
    assert not bag
    assert bag._alias_dict == {}


def test_command_flow_find_then_take():
    """The command flow works when a handler finds by name, takes by object."""
    room_items = Bag({Item("brass lamp", "lamp"), Item("rusty key", "key")})
    inventory = Bag()

    @when("take ITEM")
    def take(item):
        obj = room_items.find(item)
        if obj is None:
            say("There is no %s here." % item)
            return
        inventory.add(room_items.take(obj))

    # Round 1: take by name via the command dispatcher.
    _handle_command("take lamp")
    assert "brass lamp" in inventory
    assert "lamp" not in room_items

    # Round 2: a failed take prints a message and corrupts nothing.
    before = _bag_snapshot(room_items)
    _handle_command("take chandelier")
    assert _bag_snapshot(room_items) == before

    # Round 3: the failure did not break the following successful take.
    _handle_command("take key")
    assert "rusty key" in inventory
    assert not room_items


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
