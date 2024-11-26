from app_state import state, State, on
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pytest
import app_state


class Widget:
    @on('state.countries')
    def do_stuff(self):
        pass


@on('state.countries.AU')
def on_au():
    australia_handler()

def australia_handler():
    pass


@pytest.fixture(autouse=True)
def clean_state():
    state.reset()


def test_update(mocker):
    widget = Widget()

    mocker.spy(widget, 'do_stuff')
    mocker.spy(__import__(__name__), 'australia_handler')

    state.countries = None       # triggers state.countries.AU
    state.countries = {'AU': 4}  # triggers state.countries.AU
    state.countries['RU'] = 5
    state.countries.US = 6
    
    assert widget.do_stuff.call_count == 4
    assert australia_handler.call_count == 2
    
    state.countries.update({'RU': 6, 'US': 8})
    
    assert widget.do_stuff.call_count == 5
    

def test_autopersist(tmp_path: Path):
    state.autopersist(tmp_path / 'state.db.shelve', timeout=0)

    assert state == {}

    state.countries = [{'id': 'AU', 'questions': [ {'id': 1} ]}]

    for country in state.countries:
        country.value = 9

    assert state == {'countries': [
        {'id': 'AU', 'questions': [ {'id': 1} ]}
    ]}

    state.reload(tmp_path / 'state.db.shelve')

    assert state == {'countries': [
        {'id': 'AU', 'questions': [ {'id': 1} ]}
    ]}




