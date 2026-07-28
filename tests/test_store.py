import pytest

from unpaster import dpapi, store


@pytest.fixture()
def path(tmp_path):
    return tmp_path / "snippets.dat"


def test_load_missing_file_gives_empty_store(path):
    st, warnings = store.SnippetStore.load(path)
    assert st.snippets == []
    assert warnings == []


def test_add_assigns_id_and_order(path):
    st, _ = store.SnippetStore.load(path)
    first = st.add("admin_user", "svc-admin")
    second = st.add("port", "3389")
    assert first.id != second.id
    assert (first.order, second.order) == (0, 1)


def test_add_defaults_to_not_secret(path):
    st, _ = store.SnippetStore.load(path)
    assert st.add("port", "3389").secret is False


def test_save_then_load_round_trips(path):
    st, _ = store.SnippetStore.load(path)
    st.add("admin_user", "svc-admin", secret=True)
    st.add("port", "3389")
    st.save()

    reloaded, warnings = store.SnippetStore.load(path)
    assert warnings == []
    assert [s.name for s in reloaded.snippets] == ["admin_user", "port"]
    assert reloaded.snippets[0].secret is True
    assert reloaded.snippets[0].body == "svc-admin"


def test_saved_file_is_encrypted(path):
    st, _ = store.SnippetStore.load(path)
    st.add("admin_user", "hunter2")
    st.save()
    raw = path.read_bytes()
    assert b"hunter2" not in raw
    assert b"admin_user" not in raw


def test_saved_file_needs_the_baked_entropy(path):
    st, _ = store.SnippetStore.load(path)
    st.add("admin_user", "hunter2")
    st.save()
    with pytest.raises(dpapi.DpapiError):
        dpapi.unprotect(path.read_bytes(), b"wrong entropy")


def test_update_changes_fields(path):
    st, _ = store.SnippetStore.load(path)
    snippet = st.add("old", "body")
    st.update(snippet.id, name="new", secret=True)
    assert st.get(snippet.id).name == "new"
    assert st.get(snippet.id).secret is True
    assert st.get(snippet.id).body == "body"


def test_update_unknown_id_raises(path):
    st, _ = store.SnippetStore.load(path)
    with pytest.raises(KeyError):
        st.update("nope", name="x")


def test_delete_removes_and_renumbers(path):
    st, _ = store.SnippetStore.load(path)
    a = st.add("a", "1")
    st.add("b", "2")
    st.add("c", "3")
    st.delete(a.id)
    assert [s.name for s in st.snippets] == ["b", "c"]
    assert [s.order for s in st.snippets] == [0, 1]


def test_move_reorders_and_renumbers(path):
    st, _ = store.SnippetStore.load(path)
    st.add("a", "1")
    st.add("b", "2")
    c = st.add("c", "3")
    st.move(c.id, 0)
    assert [s.name for s in st.snippets] == ["c", "a", "b"]
    assert [s.order for s in st.snippets] == [0, 1, 2]


def test_move_clamps_out_of_range_index(path):
    st, _ = store.SnippetStore.load(path)
    a = st.add("a", "1")
    st.add("b", "2")
    st.move(a.id, 99)
    assert [s.name for s in st.snippets] == ["b", "a"]


def test_search_is_case_insensitive_substring_on_name(path):
    st, _ = store.SnippetStore.load(path)
    st.add("admin_user", "x")
    st.add("SVC_Account", "y")
    assert [s.name for s in st.search("svc")] == ["SVC_Account"]
    assert [s.name for s in st.search("_")] == ["admin_user", "SVC_Account"]


def test_search_never_matches_body(path):
    st, _ = store.SnippetStore.load(path)
    st.add("admin_user", "hunter2")
    assert st.search("hunter2") == []


def test_empty_search_returns_everything_in_order(path):
    st, _ = store.SnippetStore.load(path)
    st.add("a", "1")
    st.add("b", "2")
    assert [s.name for s in st.search("")] == ["a", "b"]


def test_corrupt_file_is_backed_up_not_destroyed(path):
    path.write_bytes(b"this is not a dpapi blob")
    st, warnings = store.SnippetStore.load(path)
    assert st.snippets == []
    assert len(warnings) == 1
    backup = path.with_name("snippets.dat.bad-1")
    assert backup.read_bytes() == b"this is not a dpapi blob"
    assert backup.name in warnings[0]


def test_repeated_corruption_increments_backup_number(path):
    path.write_bytes(b"garbage one")
    store.SnippetStore.load(path)
    path.write_bytes(b"garbage two")
    store.SnippetStore.load(path)
    assert path.with_name("snippets.dat.bad-1").read_bytes() == b"garbage one"
    assert path.with_name("snippets.dat.bad-2").read_bytes() == b"garbage two"


def test_valid_blob_with_bad_json_is_also_backed_up(path):
    path.write_bytes(dpapi.protect(b"{not json", store.ENTROPY))
    st, warnings = store.SnippetStore.load(path)
    assert st.snippets == []
    assert len(warnings) == 1
