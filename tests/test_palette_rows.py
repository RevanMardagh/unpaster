from unpaster import store
from unpaster.ui import palette


def make_store(tmp_path):
    st, _ = store.SnippetStore.load(tmp_path / "snippets.dat")
    return st


def snippet_rows(st, query):
    """The rows without the trailing Clipboard action."""
    return palette.palette_rows(st, query)[:-1]


def test_row_label_is_the_name(tmp_path):
    snippet = make_store(tmp_path).add("admin_user", "svc-admin")
    assert palette.row_label(snippet) == "admin_user"


def test_row_label_marks_secrets(tmp_path):
    snippet = make_store(tmp_path).add("db_password", "hunter2", secret=True)
    assert palette.row_label(snippet).startswith("db_password")
    assert palette.row_label(snippet) != "db_password"


def test_row_label_never_contains_the_body(tmp_path):
    snippet = make_store(tmp_path).add("db_password", "hunter2", secret=True)
    assert "hunter2" not in palette.row_label(snippet)


def test_rows_return_id_and_label_pairs(tmp_path):
    st = make_store(tmp_path)
    first = st.add("admin_user", "a")
    second = st.add("port", "b")
    assert snippet_rows(st, "") == [
        (first.id, "admin_user"),
        (second.id, "port"),
    ]


def test_rows_filter_by_query(tmp_path):
    st = make_store(tmp_path)
    st.add("admin_user", "a")
    port = st.add("port", "b")
    assert snippet_rows(st, "por") == [(port.id, "port")]


def test_no_snippet_rows_when_nothing_matches(tmp_path):
    st = make_store(tmp_path)
    st.add("admin_user", "a")
    assert snippet_rows(st, "zzz") == []


def test_rows_end_with_the_clipboard_option(tmp_path):
    st = make_store(tmp_path)
    st.add("admin_user", "a")
    assert palette.palette_rows(st, "")[-1] == (palette.CLIPBOARD_ID, "Clipboard")


def test_the_clipboard_option_stays_when_no_snippet_matches(tmp_path):
    st = make_store(tmp_path)
    st.add("admin_user", "a")
    assert palette.palette_rows(st, "zzz") == [(palette.CLIPBOARD_ID, "Clipboard")]


def test_the_clipboard_id_cannot_collide_with_a_snippet_id(tmp_path):
    snippet = make_store(tmp_path).add("admin_user", "a")
    assert snippet.id != palette.CLIPBOARD_ID
