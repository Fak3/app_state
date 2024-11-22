from app_state import state, State, on
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pytest
import app_state


class Widget:
    @on('state.regions')
    def do_stuff(self):
        print(state.regions)


@pytest.fixture(autouse=True)
def clean_state():
    state.reset()


def test_update(mocker):
    widget = Widget()
    spy = mocker.spy(widget, 'do_stuff')

    state.regions = None
    state.regions = {'AU': 4}
    state.regions['RU'] = 5
    state.regions.US = 6
    
    assert widget.do_stuff.call_count == 4
    
    state.regions.update({'RU': 6, 'US': 8})
    
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




