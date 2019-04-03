# Appstate

Minimalistic reactive local application state toolkit. 

This package provides a way to store application state in a form of single-rooted
recursive key-value tree, and means to subscribe to the changes made to the
branches of interest.

## Introduction

Let's consider a common application which has a "screen" for user to change configuration and another
"screen" which allows to perform something useful, depending on the current configuration.

If we organize our application into separate "configuration screen" module and "main screen" module, we would
have to ensure the "main screen" reacts accordingly when user changes values on "configuration screen".

Traditional methods to compose the app from the modules together includes direct function calling, 
"callbacks" pattern, "signal\slot" pattern and some others. The approach provided by this package may be
considered as a mix of "signal\slot" pattern and "reactive programming". 

To address our app case, we can make configuration screen module write any setting to the state:

```python
from app_state import state

# This should likely happen in 'OK' button click callback, not displayed here.
state.username = 'value'  
```

And we let the main screen module to subscribe to the setting by decorating a function wich will read changed 
value from state and update main screen display:

```python
from app_state import state, on

@on('state.username')
def change_user():
    title.text = 'Hello, ' + state.username
```

## Installation

```
pip install app_state
```

## Usage

```python
from app_state import state

state["some_data"] = 42  # Alternatively: state.some_data = 42
```

State is a recursive dictionary-like object. For covenience, 
branches can also be accessed with `.` as attributes.

### Listen for state changes

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

state.user = {'name': 'Alice'}  # mainwindow.on_user() will be called.
```

### Persistence

By default the state is stored in memory. But it is possible to automatically 
store the state to a file when it is changed. Call `state.autopersist('myfile')` to
enable persistence. This function will load the state from the file, and turn on automatic
storage of the state to this file.

If you want to exclude some branches from persistence, then you should store them as
attributes, starting with underscore:

```python
# `_temp_peers` will never be stored to a file
state.countries.Australia._temp_peers = [{'ip': '8.8.8.8'}]
```

## API

```python
state.autopersist(filepath, timeout=3, nursery=None)
```

Enable automatic state persistence, create a shelve with a given filepath.
If file already exists, read state from it.

`timeout` - how many seconds to wait before writing to the file after each state change.
This parameter helps to reduce frequent writes to disk, grouping changes together. Only
works when state changes happen in a thread with `asyncio` or `trio` event loop.

`nursery` - required if `trio` is used.

```python
class DictNode
```

`app_state.state` and every its subtree is an instance of `DictNode`.
Normally you don't need to use this class explicitly. Instance of `DictNode` is a dict-like 
object which emit signal when it is changed, so that functions decorated with `on()` decorator
get called appropriately.
When you create a dictionary and assign it to any state branch, it will be implicitly 
converted to `DictNode`:

```python
from app_state import state, DictNode
state.countries = {}
assert isinstance(state.countries, DictNode)  # True
```

`as_dict(full=False)`

This method returns regular dictionary, converting `DictNode` and all subnodes.

If `full` is True, then all attributes, starting with underscore will also be included
in the dictionary as keys.

```python
state.config = {'name': 'user1'}
state.config._session_start = '16:35'
print(state.config.as_dict(full=True))
# prints {'name': 'user1', '_session_start': '16:35'}
```
