from app.ids import new_id


def test_new_id_default_length():
    assert len(new_id()) == 10


def test_new_id_charset():
    ident = new_id()
    assert ident.isalnum()
    assert ident.isascii()


def test_new_id_unique():
    ids = {new_id() for _ in range(1000)}
    assert len(ids) == 1000
