from sentinel_combination.components import COMPONENTS, load_lock


def test_lock_and_component_constants_match():
    lock = load_lock()["components"]

    assert COMPONENTS["chain"].commit == lock["sentinel-chain"]["commit"]
    assert COMPONENTS["chain"].repository == lock["sentinel-chain"]["repository"]
    assert COMPONENTS["chain"].relative_path == lock["sentinel-chain"]["path"]

    assert COMPONENTS["iron"].commit == lock["sentinel-iron"]["commit"]
    assert COMPONENTS["iron"].repository == lock["sentinel-iron"]["repository"]
    assert COMPONENTS["iron"].relative_path == lock["sentinel-iron"]["path"]


def test_source_pins_are_full_commit_shas():
    for component in COMPONENTS.values():
        assert len(component.commit) == 40
        assert all(character in "0123456789abcdef" for character in component.commit)
