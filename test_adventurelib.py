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


def bag_snapshot(bag):
    """Take a deep-copy snapshot of a Bag's observable state.

    State is captured by value (item aliases) rather than identity, so the
    snapshot survives comparison against the live bag.
    """
    deep_items = copy.deepcopy(list(bag))
    return {
        "items": sorted(i.aliases for i in deep_items),
        "aliases": {
            k: sorted(i.aliases for i in v) for k, v in bag._alias_dict.items()
        },
    }


def assert_bag_unchanged(bag, snapshot):
    """Assert a bag is field-for-field identical to its snapshot."""
    assert sorted(i.aliases for i in bag) == snapshot["items"]
    assert {
        k: sorted(i.aliases for i in v) for k, v in bag._alias_dict.items()
    } == snapshot["aliases"]


def test_bag_find_by_object():
    """find() accepts an Item object as well as a name."""
    item = Item("sword", "blade")
    other = Item("shield")
    bag = Bag({item, other})
    assert bag.find(item) is item
    assert bag.find(other) is other


def test_bag_find_object_not_present():
    """find() with an Item that is not in the bag returns None."""
    bag = Bag({Item("sword")})
    assert bag.find(Item("sword")) is None


def test_bag_take_found_object():
    """Taking an object previously returned by find() works (the bug)."""
    item = Item("rusty mallet", "mallet")
    bag = Bag({item})
    found = bag.find("mallet")
    assert found is item
    taken = bag.take(found)
    assert taken is item
    assert item not in bag
    assert not bag


@pytest.mark.parametrize("key", ["sword", "Sword", "blade"])
def test_bag_take_by_name_still_works(key):
    """Passing a name to take() keeps working, case insensitively."""
    item = Item("Sword", "blade")
    bag = Bag({item})
    assert bag.take(key) is item
    assert not bag


@pytest.mark.parametrize("bad", [None, 42, 3.14, object(), ["sword"], ("sword",)])
def test_bag_find_invalid_argument_type(bad):
    """find() raises a readable TypeError for non-str, non-Item arguments."""
    bag = Bag({Item("sword")})
    snapshot = bag_snapshot(bag)
    with pytest.raises(TypeError, match="requires an item name"):
        bag.find(bad)
    assert_bag_unchanged(bag, snapshot)


@pytest.mark.parametrize("bad", [None, 42, 3.14, object(), ["sword"], ("sword",)])
def test_bag_take_invalid_argument_type_rolls_back(bad):
    """A rejected take() leaves the bag field-for-field unchanged."""
    item = Item("sword", "blade")
    bag = Bag({item, Item("shield")})
    snapshot = bag_snapshot(bag)
    with pytest.raises(TypeError, match="requires an item name"):
        bag.take(bad)
    assert_bag_unchanged(bag, snapshot)


@pytest.mark.parametrize("method", ["find", "take"])
def test_bag_missing_item_returns_none(method):
    """Looking up an absent item returns None instead of raising."""
    bag = Bag({Item("sword")})
    snapshot = bag_snapshot(bag)
    assert getattr(bag, method)("dragon") is None
    assert getattr(bag, method)(Item("dragon")) is None
    assert_bag_unchanged(bag, snapshot)


def test_bag_take_from_empty_bag():
    """Taking from an empty bag (insufficient resources) returns None."""
    bag = Bag()
    assert bag.take("anything") is None
    assert bag.take(Item("anything")) is None
    assert bag.find("anything") is None


def test_bag_take_repeated_calls():
    """Taking the same name twice: the second call finds nothing."""
    item = Item("coin")
    bag = Bag({item})
    assert bag.take("coin") is item
    assert bag.take("coin") is None
    assert bag.take(item) is None
    assert not bag


def test_bag_find_repeated_calls_idempotent():
    """find() does not mutate the bag, however often it is called."""
    item = Item("gem", "jewel")
    bag = Bag({item})
    snapshot = bag_snapshot(bag)
    for _ in range(5):
        assert bag.find("gem") is item
        assert bag.find(item) is item
    assert_bag_unchanged(bag, snapshot)


def test_bag_take_partial_completion():
    """Taking one of several items leaves the rest fully intact."""
    sword = Item("sword", "blade")
    shield = Item("shield")
    bag = Bag({sword, shield})
    assert bag.take(sword) is sword
    assert shield in bag
    assert "shield" in bag
    assert "sword" not in bag
    assert bag.find("blade") is None
    assert set(bag._alias_dict) == {"shield"}


def test_bag_out_of_order_input_deterministic():
    """The same items added in different orders give identical results."""
    names = ["apple", "banana", "cherry", "date"]
    results = []
    for order in (names, names[::-1], [names[2], names[0], names[3], names[1]]):
        bag = Bag(Item(n) for n in order)
        outcome = [bag.find(n).name for n in names]
        outcome += [bag.take(names[1]).name, bag.take(names[3]).name]
        outcome.append(sorted(i.name for i in bag))
        results.append(outcome)
    assert results[0] == results[1] == results[2]


def test_bag_same_input_sequence_replay():
    """Replaying the same operation sequence gives the same outcome."""

    def run():
        bag = Bag({Item("rock"), Item("paper"), Item("scissors")})
        log = []
        log.append(bag.take("paper"))
        log.append(bag.take("missing"))
        log.append(bag.find("rock"))
        log.append(bag.take(bag.find("scissors")))
        log.append(bag.take("rock"))
        log.append(bag.take("rock"))
        return [str(x) for x in log], sorted(str(i) for i in bag)

    first, first_remaining = run()
    second, second_remaining = run()
    assert first == second
    assert first_remaining == second_remaining == []


def test_bag_failed_take_then_success():
    """A failed take does not disturb a subsequent successful take."""
    item = Item("key")
    bag = Bag({item})
    assert bag.take("lock") is None
    with pytest.raises(TypeError):
        bag.take(None)
    assert bag.take("key") is item
    assert not bag


def test_bag_alias_dict_does_not_grow_unbounded():
    """Adding and removing many items leaves no residue in the alias dict."""
    bag = Bag()
    for i in range(200):
        bag.add(Item("item %d" % i, "alias %d" % i))
    assert len(bag._alias_dict) == 400
    for i in range(200):
        assert bag.take("item %d" % i) is not None
    assert not bag
    assert bag._alias_dict == {}


def test_bag_single_element_boundary():
    """A single-element bag supports find/take by name and by object."""
    item = Item("only")
    bag = Bag({item})
    assert bag.find("only") is item
    assert bag.take(item) is item
    assert bag.take("only") is None


def test_bag_find_ambiguous_alias_deterministic():
    """With several items sharing an alias, find() is stable across replays."""

    def run():
        bag = Bag({Item("red gem", "gem"), Item("blue gem", "gem")})
        return str(bag.find("gem"))

    assert run() == run()


def test_inventory_room_command_flow():
    """The take/drop command flow stays consistent across rooms and inventory."""
    inventory = Bag()
    hall = Room("A hall.")
    hall.items = Bag({Item("torch", "light")})
    state = {"room": hall}

    @when("take ITEM")
    def take_cmd(item):
        obj = state["room"].items.take(item)
        if obj:
            inventory.add(obj)

    @when("drop ITEM")
    def drop_cmd(item):
        obj = inventory.take(item)
        if obj:
            state["room"].items.add(obj)

    _handle_command("take torch")
    assert "torch" in inventory
    assert not hall.items

    # Repeated take of an item no longer in the room is a no-op.
    _handle_command("take torch")
    assert len(inventory) == 1

    _handle_command("drop torch")
    assert not inventory
    assert "torch" in hall.items

    # Out-of-order and repeated commands over several turns stay consistent.
    for _ in range(3):
        _handle_command("take light")
        _handle_command("drop torch")
    assert "torch" in hall.items
    assert not inventory

    # Taking via a found object works through the same Bag used by commands.
    found = hall.items.find("torch")
    assert hall.items.take(found) is found
    assert not hall.items
