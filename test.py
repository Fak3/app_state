from app_state import state, State, on
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pytest
import app_state


class Widget:
    @on('state.countries')
    def on_countries(self):
        pass


@on('state.countries.AU')
def on_au():
    australia_handler()

def australia_handler():
    pass


@pytest.fixture(autouse=True)
def clean_state():
    # Stop autopersist
    for handler in list(on.handlers['state.']):
        if handler.__qualname__ == 'State.autopersist.<locals>.persist':
            on.handlers['state.'].remove(handler)

    state.reset()


def test_assign_with_intermediate_node(mocker):
    assert state == {}
    state.countries.RU.data = 3
    assert state == {'countries': {'RU': {'data': 3}}}

    state.regions = [{'ru_77': {'data': 'yes'}}]
    assert state['regions'] == [{'ru_77': {'data': 'yes'}}]
    assert state == {
        'countries': {'RU': {'data': 3}},
        'regions': [{'ru_77': {'data': 'yes'}}]
    }


def test_update(mocker):
    widget = Widget()

    mocker.spy(widget, 'on_countries')
    mocker.spy(__import__(__name__), 'australia_handler')

    state.countries = None
    assert widget.on_countries.call_count == 1
    assert australia_handler.call_count == 1

    state.countries = {'AU': 4}
    assert widget.on_countries.call_count == 2
    assert australia_handler.call_count == 2

    state.countries['RU'] = 5
    state.countries.US = 6

    assert widget.on_countries.call_count == 4
    assert australia_handler.call_count == 2
    
    state.countries.update({'RU': 6, 'US': 8})
    
    assert widget.on_countries.call_count == 5
    

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


def test_get():
    state.countries = {'AU': {'questions': [ {'id': 1} ]}}

    au = state.countries.AU

    assert au._appstate_path == 'state.countries.AU'
    assert state.countries.AU == au

    au.answers = 123
    assert state.countries.AU.answers == 123

    assert state == {'countries' : {'AU': {
        'questions': [  {'id': 1}, ],
        'answers': 123
    }}}

    au = state.countries['AU']

    au.answers = 'none'
    assert state.countries.AU.answers == 'none'

    # TODO: lists don't get updated yet
    au.questions.append(456)

    au = state.countries.get('AU')

    au.questions.append('789')

    assert state == {'countries' : {'AU': {
        'questions': [  {'id': 1}, ],
        'answers': 'none'
    }}}


