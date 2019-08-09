from app_state import state, on
from unittest.mock import Mock, patch, MagicMock


class Widget:
    @on('state.regions')
    def do_stuff(self):
        print(state.regions)
        


def test_update(mocker):
    widget = Widget()
    spy = mocker.spy(widget, 'do_stuff')
    state.regions = None
    state.regions = {'AU': 4}
    state.regions['RU'] = 5
    
    assert widget.do_stuff.call_count == 3
    
    state.regions.update({'RU': 6, 'US': 8})
    
    assert widget.do_stuff.call_count == 4
    
