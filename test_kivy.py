from app_state import state, State, on
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from asyncio import sleep
import pytest
import app_state
import asyncio
from kivy.lang import Builder
from kivy.app import App
from kivy.base import stopTouchApp, async_runTouchApp
from kivy.tests.async_common import UnitKivyApp, UnitTestTouch
from kivy.uix.boxlayout import BoxLayout


Builder.load_string('''
#:import state app_state.state

<MainWidget>:
    Button:
        id: button
        text: "click me"
        # on_press: label.text = "Clicked!"; print('clicked')
        on_press: state.user.name = 'Clicked'

    Label:
        id: label
        text: str(state.user.name)
        # on_text: print('TXTXT')

''')


@on('state.user.name')
def x():
    print(f'{state.user.name=}')

class MainWidget(BoxLayout):
    pass


class MyApp(App, UnitKivyApp):
    app_has_started = False

    def __init__(self, statefile, *a, **kw):
        super().__init__(*a, **kw)
        state.autopersist(statefile, timeout=0)
        # print(f'app created: {self}')

    def build(self):
        # print('Build started')
        self.mainwidget = MainWidget()
        return self.mainwidget

    async def async_run(self):
        self._run_prepare()
        await async_runTouchApp()
        self.stop()


    async def click(self, widget):
        """ Test helper to simulate clicks """
        await sleep(0.1)

        # Wait for widget to be enabled
        for x in range(20):
            if getattr(widget, 'disabled', False) is False:
                break
            await sleep(0.1)
        else:
            raise Exception(f'Widget {widget} is disabled')

        text = getattr(widget, 'text', '') or getattr(widget, 'hint_text', '')
        # print(f'Click {widget} "{text}"')

        parent = widget.parent
        pos = widget.center
        touch = UnitTestTouch(
            *widget.to_window(*widget.center)
        )

        touch.touch_down()
        touch.touch_up()
        await sleep(0.1)


# @pytest.fixture(autouse=True)
# def clean_state():
#     state.reset()


@pytest.mark.asyncio
async def test_kivy(tmp_path: Path):
    state.reset()
    app = MyApp(statefile = tmp_path / 'state.db.shelve')

    assert state == {}

    loop = asyncio.get_event_loop()
    task = loop.create_task(app.async_run())

    await sleep(0.1)

    # Initially displayed state.user.name is empty
    assert app.mainwidget.ids.label.text == ''

    state.user.name = 'Bob'

    await sleep(0.1)

    assert app.mainwidget.ids.label.text == 'Bob'

    await app.click(app.mainwidget.ids['button'])

    await sleep(0.1)
    assert app.mainwidget.ids.label.text == 'Clicked'

    await sleep(0.1)
    stopTouchApp()
    await task
    await sleep(0.1)


    return



