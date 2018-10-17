Minimalistic reactive local application state toolkit. 


## Installation

```
pip install app_state
```

## Usage

```python
from app_state import state

state["some_data"] = 42  # Alternatively: state.some_data = 42
```

State is a dictionary-like object, representing a tree of sub-dictionaries. For 
covenience, branches can also be accessed with `.` as attributes.

`@on(*patterns)` decorator makes the decorated function or method to be called each
time when the state subtree changes. Each `pattern` is a dot-separated string, representing
state subtree path.

```python
from app_state import state, on

@on('state.countries')
def countries():
    print(f'countries changed to: {state.countries}')
    
@on('state.countries.Australia.population')
def au_population():
    population = state.get('countries', {}).get('Australia', {}).get('population')
    print(f'Australia population now: {population}')
    
state.countries = {'Australia': {'code': 'AU'}, 'Brazil': {}}
state.countries.Australia.population = 4500000
    
```
will print:

```
countries changed to: {'Australia': {'code': 'AU'}, 'Brazil': {}}
Australia population now: None
countries changed to: {'Australia': {'code': 'AU', 'population': 4500000}, 'Brazil': {}}
Australia population now: 4500000
```

`@on()` can wrap a method of a class. When state changes, that method will be called for
every instance of this class.

```python
from app_state import state, on

class MainWindow:
    @on('state.user')
    def on_user(self):
        self.settext(f'Welcome, {state.user.name}')

mainwindow = MainWindow()

state.user = {'name': 'Alice'}
```
