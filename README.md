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

state.user = {'name': 'Alice'}
```

### Persistence

By default the state is stored only in memory. But it is possible to automatically 
store the state to a file after it was changed. Call `state.autopersist('myfile')` to
enable persistence. This function will load the state from the file, and turn on automatic
storage of the state to this file.

Currently automatic persistence requires use of `asyncio` or `trio`.

If you want some branches to exclude from persistence, then you should store them as
attributes, starting with underscore:

```python
# _temp_peers will never be stored to a file
state.countries.Australia._temp_peers = [{'ip': '8.8.8.8'}]
```

## API

```python
state.autopersist(filepath, timeout=3, nursery=None)
```

Enable automatic state persistence, create a shelve with a given filepath.
If file already exists, read state from it.

`timeout` - how many seconds to wait before writing to the file after each state change.
This parameter helps to reduce frequent writes to disk, grouping changes together.

`nursery` - required if `trio` is used instead of `asyncio`.

```python
class DictNode
```

`app_state.state` and every its subtree is an instance of `DictNode`.
Normally you don't need to use this class explicitly. Instance of `DictNode` is a dict-like 
object which emit signal when it is changed, so that functions decorated with `on()` decorator
get called appropriately.
When you create a dictionary and assign to any state branch, it will be implicitly 
converted to `DictNode`.

```python
from app_state import state, DictNode
state.countries = {}
assert isinstance(state.countries, DictNode)  # True
```

`as_dict(full=False)`

This method returns `DictNode` and all subnodes, converted to a regular dictionary.

If `full` is True, then all attributes, starting with underscore will also be included
in the dictionary as keys.

```python
state.config = {'name': 'user1'}
state.config._session_start = '16:35'
print(state.config.as_dict(full=True))
# prints {'name': 'user1', '_session_start': '16:35'}
```
