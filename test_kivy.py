#!/usr/bin/env python
from app_state import state, on
from unittest.mock import Mock, patch, MagicMock
#from kivy import 


from kivy.app import App
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty


mainwidget = """
#:import state app_state.state

BoxLayout:
    Label:
        text: "Hello, " + str(state.username)
    TextInput:
        on_text: state.username = self.text
"""

    

#root = 
    
class MyApp(App):
    def build(self):
        state._appstate_autocreate = True
        #mainwidget = MainWidget()
        #mainwidget.add_widget(HighLabel())  # ! This label will also have height: dp(20) and text: 'height dp(20)'
        return Builder.load_string(mainwidget)

if __name__ == '__main__':
    MyApp().run()
