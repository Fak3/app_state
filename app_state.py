import inspect
import asyncio
import shelve
from collections import defaultdict
from copy import copy
from functools import update_wrapper, partial


try:
    import trio
except ImportError:
    pass

from getinstance import InstanceManager
from lockorator.asyncio import lock_or_exit
from sniffio import current_async_library


class DictNode(dict):
    def __repr__(self):
        return repr(self.as_dict(full=True))
    
    def _make_subnode(self, key, value, signal=True):
        if not isinstance(value, dict):
            return value
        if isinstance(value, DictNode):
            return value
        
        node = DictNode(value)
        node._appstate_path = f'{self._appstate_path}.{key}'
        for k, v in node.items():
            node.__setitem__(k, v, signal=False)
        return node
        
    def __getattribute__(self, name):
        if name.startswith('_') or name in self.__dict__:
            return super().__getattribute__(name)

        try:
            result = self[name]
        except KeyError:
            return super().__getattribute__(name)
        return result

    def __delitem__(self, key):
        super().__delitem__(key)
        state.signal(f'{self._appstate_path}.{key}')

    def setdefault(self, key, value):
        if key not in self:
            self[key] = value
        return self[key]
    
    def __setitem__(self, key, value, signal=True):
        node = self._make_subnode(key, value, signal)
        super().__setitem__(key, node)
        
        #print('setitem ', key, value)
        if signal:
            state.signal(f'{self._appstate_path}.{key}')
            #print(f'signal {self._appstate_path}.{key}')

    def __setattr__(self, name, value):
        if name.startswith('_appstate_'):
            return super().__setattr__(name, value)
        
        node = self._make_subnode(name, value)
        
        if name.startswith('_'):
            super().__setattr__(name, node)
            state.signal(f'{self._appstate_path}.{name}')
            #print(f'signal {self._appstate_path}.{name}')
        else:
            self.__setitem__(name, node)
            
            
    def as_dict(self, full=False):
        result = {}
        for k, v in self.items():
            if isinstance(v, DictNode):
                result[k] = v.as_dict(full=full)
            else:
                result[k] = v
        
        if not full:
            return result
        
        for k, v in self.__dict__.items():
            if not k.startswith('_appstate_') and k.startswith('_'):
                if isinstance(v, DictNode):
                    result[k] = v.as_dict(full=full)
                else:
                    result[k] = v
        return result


class State(DictNode):
    def __init__(self):
        super().__init__()
        self._appstate_lazy_watchlist = []
        self._appstate_funcwatchlist = defaultdict(list)
        self._appstate_classwatchlist = defaultdict(list)
        self._appstate_path = 'state'

    def call(self, f, *a, **kw):
        if not inspect.iscoroutinefunction(f):
            return f(*a, **kw)
        
        if current_async_library() == 'trio':
            if not getattr(state, '_nursery'):
                raise Exception('Provide state._nursery for async task to run.')
            state._nursery.start_soon(f)
        else:
            return asyncio.create_task(f())
        
    def signal(self, path):
        #print(path, self._lazy_watchlist, dict(self._classwatchlist))
        for f, patterns in self._appstate_lazy_watchlist:
            module = inspect.getmodule(f)
            cls = getattr(module, f.__qualname__.split('.')[0])

            if cls and hasattr(cls, f.__name__):
                for pat in patterns:
                    self._appstate_classwatchlist[pat].append((cls, f))
            else:
                for pat in patterns:
                    self._appstate_funcwatchlist[pat].append(f)
        self._appstate_lazy_watchlist = []

        for watcher_pat in self._appstate_funcwatchlist:
            if watcher_pat.startswith(path) \
               or path.startswith(watcher_pat):
                for f in self._appstate_funcwatchlist[watcher_pat]:
                    self.call(f)

        for watcher_pat in copy(self._appstate_classwatchlist):
            if watcher_pat.startswith(path) \
               or path.startswith(watcher_pat):
                for cls, f in self._appstate_classwatchlist[watcher_pat]:
                    for instance in cls._appstate_instances.all():
                        self.call(f, instance)

    
    def autopersist(self, file, timeout=3, nursery=None):
        self._appstate_shelve = shelve.open(file)
        
        for k, v in self._appstate_shelve.get('state', {}).items():
            self.__setitem__(k, v, signal=True)
        
        @on('state')
        def persist():
            try:
                asynclib = current_async_library()
            except:
                state._appstate_shelve['state'] = state.as_dict()
                state._appstate_shelve.sync()
            else:
                if asynclib == 'trio':
                    #if not nursery:
                    nursery = getattr(state, '_nursery')
                    if not nursery:
                        raise Exception('Provide nursery for state persistence task to run in.')
                    nursery.start_soon(persist_delayed, timeout)
                else:
                    asyncio.create_task(persist_delayed(timeout))


@lock_or_exit()
async def persist_delayed(timeout):
    if current_async_library() == 'trio':
        await trio.sleep(timeout)
    else:
        await asyncio.sleep(timeout)
    #print('PERSIST', state)
    state._appstate_shelve['state'] = state.as_dict()
    state._appstate_shelve.sync()
        

class FunctionWrapper:
    """
    If wrapped callable is a regular function, this wrapper does nothing.
    If wrapped callable is a method, it will ensure that owner class has
    a member `_appstate_instances` which is an InstanceManager.
    """
    def __init__(self, f):
        self.f = f
        update_wrapper(self, f)

    def __call__(self, *a, **kw):
        return self.f(*a, **kw)
        
    def __set_name__(self, owner, name):
        if not hasattr(owner, '_appstate_instances'):
            owner._appstate_instances = InstanceManager(owner, '_appstate_instances')
        setattr(owner, self.f.__name__, self.f)


class on:
    """
    Decorator. The decorated function or method will be called each time when any 
    of the provided state patterns changes.
    """
    def __init__(self, *patterns):
        self.patterns = patterns

    def __call__(self, f):
        wrapped = FunctionWrapper(f)
        state._appstate_lazy_watchlist.append((f, self.patterns))
        return wrapped


state = State()
