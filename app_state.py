import inspect
from collections import defaultdict
from copy import copy
from functools import update_wrapper

from getinstance import InstanceManager


class StateNode(dict):
    def __init__(self, data=None):
        self._data = {} if data is None else data

    def __str__(self):
        return self._data.__str__()

    def __getattribute__(self, name):
        if name.startswith('_') or name in self.__dict__:
            return super().__getattribute__(name)

        try:
            result = self._data[name]
        except KeyError:
            return super().__getattribute__(name)
        if not isinstance(result, dict):
            return result
        result = StateNode(result)
        result.__dict__['_path'] = f'{self._path}.{name}'
        return result

    def get(self, *a, **kw):
        return self._data.get(*a, **kw)
    
    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value
        state.trigger(f'{self._path}.{key}')

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            self._data.__setitem__(name, value)
            state.trigger(f'{self._path}.{name}')


class State(StateNode):
    def __init__(self):
        self._lazy_watchlist = []
        self._classwatchlist = defaultdict(list)
        self._funcwatchlist = defaultdict(list)
        self._path = 'state'
        super().__init__()

    def trigger(self, path):
        #print(path, self._lazy_watchlist, dict(self._classwatchlist))
        for f, patterns in self._lazy_watchlist:
            module = inspect.getmodule(f)
            cls = getattr(module, f.__qualname__.split('.')[0])

            if cls and hasattr(cls, f.__name__):
                for pat in patterns:
                    self._classwatchlist[pat].append((cls, f))
            else:
                for pat in patterns:
                    self._funcwatchlist[pat].append(f)
        self._lazy_watchlist = []

        for watcher_pat in self._funcwatchlist:
            if watcher_pat.startswith(path) \
               or path.startswith(watcher_pat):
                for f in self._funcwatchlist[watcher_pat]:
                    f()

        for watcher_pat in copy(self._classwatchlist):
            if watcher_pat.startswith(path) \
               or path.startswith(watcher_pat):
                for cls, f in self._classwatchlist[watcher_pat]:
                    for instance in cls._appstate_instances.all():
                        f(instance)



class FunctionWrapper:
    def __init__(self, f):
        self.f = f
        update_wrapper(self, f)

    def __call__(self, *a, **kw):
        return self.f(*a, **kw)

    def __set_name__(self, owner, name):
        if not hasattr(owner, '_appstate_instances'):
            owner._appstate_instances = InstanceManager(owner)


class on:
    """
    Decorator. The decorated function or method will be called each time when any 
    of the provided state patterns changes.
    """
    def __init__(self, *patterns):
        self.patterns = patterns

    def __call__(self, f):
        wrapped = FunctionWrapper(f)
        state._lazy_watchlist.append((wrapped, self.patterns))
        #return f
        return wrapped


state = State()
