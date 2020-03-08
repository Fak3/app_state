import inspect
import asyncio
import shelve
from collections import defaultdict
from collections.abc import Mapping
from copy import copy
from functools import update_wrapper, partial

try:
    from kivy._event import Observable
except ImportError:
    Observable = object

try:
    import trio
except ImportError:
    pass

from getinstance import InstanceManager
from lockorator.asyncio import lock_or_exit
from sniffio import current_async_library


class BaseNode:
    def _make_subnode(self, key, value, signal=True):
        if isinstance(value, (DictNode, ListNode)):
            return value
        
        if isinstance(value, Mapping):
            value = DictNode(value, path=f'{self._appstate_path}.{key}')
            #value._appstate_path = 
            for k, v in value.items():
                value.__setitem__(k, v, signal=False)
        elif isinstance(value, list):
            value = ListNode(value, path=f'{self._appstate_path}.{key}')
        return value
    
    
class ListNode(list, BaseNode):
    def __init__(self, *a, **kw):
        self._appstate_path = kw.pop('path')
        super().__init__(*a, **kw)
        
    def __iter__(self):
        for idx, item in enumerate(list.__iter__(self)):
            yield self._make_subnode(str(idx), item, signal=False)
    
    def as_list(self):
        result = []
        for item in list.__iter__(self):
            if isinstance(item, DictNode):
                result.append(item.as_dict())
            elif isinstance(item, ListNode):
                result.append(item.as_list())
            else:
                result.append(item)
        return result
    

class DictNode(Mapping, Observable, BaseNode):
    def __init__(self, *a, **kw):
        self._appstate_path = kw.pop('path')
        self._dict = dict(*a, **kw)
        
    def __iter__(self):
        return self._dict.__iter__()
    
        #return self._make_subnode(key, item, signal=False)
    
    def __len__(self):
        return self._dict.__len__()
    
    #@property
    #def __class__(self):
        #return type('DictNode', (Observable,dict), {}) 
        
    def __repr__(self):
        return repr(self.as_dict(full=True))
    
        
    def __getattribute__(self, name):
        if (name.startswith('_') 
            or name in self.__dict__ 
            or name in DictNode.__dict__ 
            or name in State.__dict__ 
            or name in ['proxy_ref', 'fbind']):
            return super().__getattribute__(name)

        try:
            result = self[name]
        except KeyError:
            
            if state._appstate_autocreate:
                result = self._make_subnode(name, {}, signal=False)
                self[name] = result
                return result
            else:
                return super().__getattribute__(name)
        return result

    def items(self):
        return self._dict.items()
        
    def __delitem__(self, key):
        self._dict.__delitem__(key)
        state.signal(f'{self._appstate_path}.{key}')

    def update(self, *a, **kw):
        changed = False
        if len(a) > 1:
            raise TypeError(f'update expected at most 1 arguments, got {len(a)}')
        if a:
            if hasattr(a[0], 'keys'):
                for key in a[0]:
                    if key not in self or not self[key] == a[0][key]:
                        changed = True
                        #print(key, a[0][key])
                        self.__setitem__(key, a[0][key], signal=False)
            else:
                for k, v in a[0]:
                    if k not in self or not self[k] == v:
                        changed = True
                        self.__setitem__(k, v, signal=False)
                    
        for key in kw:
            if key not in self or not self[key] == kw[key]:
                changed = True
                self.__setitem__(key, kw[key], signal=False)
                
        if changed:
            state.signal(f'{self._appstate_path}')
        
    def setdefault(self, key, value):
        if key not in self:
            self[key] = value
        return self[key]
    
    def __getitem__(self, key):
        #try:
        item = self._dict.__getitem__(key)
        return self._make_subnode(key, item, signal=False)
        #except KeyError:
            #if state._appstate_autocreate:
                #result = self._make_subnode(key, {}, signal=False)
                #self[key] = result
                #return result
            #else: 
                #raise
                
    def __bool__(self):
        return bool(self._dict)
    
    def __hash__(self, *a, **kw):
        return hash(None)
    
    def __lt__(self, other):
        return True
    def __le__(self, other):
        return True
    def __eq__(self, other):
        return self._dict.__eq__(other)
    def __ne__(self, other):
        return self._dict.__ne__(other)
    def __gt__(self, other):
        return True
    def __ge__(self, other):
        return True

    def __contains__(self, *a, **kw):
        return self._dict.__contains__(*a, **kw)
    
    def get(self, *a, **kw):
        #print(f'get {a}, {kw}')
        return self._dict.get(*a, **kw)
    
    def keys(self, *a, **kw):
        return self._dict.keys(*a, **kw)
    
    def values(self, *a, **kw):
        for key, value in self._dict.items(*a, **kw):
            yield self._make_subnode(key, value, signal=False)
                
    
    #def setdefault(self, *a, **kw):
        #return self._dict.setdefault(*a, **kw)
    
    def pop(self, *a, **kw):
        return self._dict.pop(*a, **kw)
    
    def popitem(self, *a, **kw):
        return self._dict.popitem(*a, **kw)
    
    def fromkeys(self, *a, **kw):
        return self._dict.fromkeys(*a, **kw)
    
    def clear(self, *a, **kw):
        return self._dict.clear(*a, **kw)
    
    def copy(self, *a, **kw):
        return self._dict.copy(*a, **kw)
    
    def __setitem__(self, key, value, signal=True):
        node = self._make_subnode(key, value, signal)
        self._dict.__setitem__(key, node)
        
        #print('setitem ', key, value)
        if signal:
            state.signal(f'{self._appstate_path}.{key}')
            #print(f'signal {self._appstate_path}.{key}')

    def __setattr__(self, name, value):
        if name.startswith('_appstate_') or name == '_dict':
            return super().__setattr__(name, value)
        
        node = self._make_subnode(name, value)
        
        if name.startswith('_'):
            super().__setattr__(name, node)
            state.signal(f'{self._appstate_path}.{name}')
            #print(f'signal {self._appstate_path}.{name}')
        else:
            self.__setitem__(name, node)
            
    def __str__(self):
        return self._dict.__str__()
    
    def as_dict(self, full=False):
        result = {}
        for k, v in self.items():
            if isinstance(v, DictNode):
                result[k] = v.as_dict(full=full)
            elif isinstance(v, ListNode):
                result[k] = v.as_list()
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

    @property
    def proxy_ref(self):
        return self
    
    def bind(self, **kwargs):
        pass

    def unbind(self, **kwargs):
        pass

    #def fbind(self, childname, callback, args):
        
    def fbind(self, name, func, *largs, **kwargs):
        '''See :meth:`EventDispatcher.fbind`.

        .. note::

            To keep backward compatibility with derived classes which may have
            inherited from :class:`Observable` before, the
            :meth:`fbind` method was added. The default implementation
            of :meth:`fbind` is to create a partial
            function that it passes to bind while saving the uid and largs/kwargs.
            However, :meth:`funbind` (and :meth:`unbind_uid`) are fairly
            inefficient since we have to first lookup this partial function
            using the largs/kwargs or uid and then call :meth:`unbind` on
            the returned function. It is recommended to overwrite
            these methods in derived classes to bind directly for
            better performance.

            Similarly to :meth:`EventDispatcher.fbind`, this method returns
            0 on failure and a positive unique uid on success. This uid can be
            used with :meth:`unbind_uid`.

        '''
        #uid = self.bound_uid
        ##self.bound_uid += 1
        f = partial(func, *largs, **kwargs, instance=None, v=None)
        #self.__fbind_mapping[name].append(((func, largs, kwargs), uid, f))
        print(f"KV {self._appstate_path}.{name}")
        state._appstate_lazy_kvlang_watchlist.append((f, [f'{self._appstate_path}.{name}']))
        #try:
            #self.bind(**{name: f})
            #return uid
        #except KeyError:
            #return 0
        return 1

    def funbind(self, name, func, *largs, **kwargs):
        '''See :meth:`fbind` and :meth:`EventDispatcher.funbind`.
        '''
        print(f'funbind {self} {name} {func}')
        #cdef object f = None
        #cdef tuple item, val = (func, largs, kwargs)
        #cdef list bound = self.__fbind_mapping[name]

        #for i, item in enumerate(bound):
            #if item[0] == val:
                #f = item[2]
                #del bound[i]
                #break

        #if f is not None:
            #try:
                #self.unbind(**{name: f})
            #except KeyError:
                #pass

    def unbind_uid(self, name, uid):
        '''See :meth:`fbind` and :meth:`EventDispatcher.unbind_uid`.
        '''
        print(f'unbind_uid {self} {name} {uid}')
        #cdef object f = None
        #cdef tuple item
        #cdef list bound = self.__fbind_mapping[name]
        #if not uid:
            #raise ValueError(
                #'uid, {}, that evaluates to False is not valid'.format(uid))

        #for i, item in enumerate(bound):
            #if item[1] == uid:
                #f = item[2]
                #del bound[i]
                #break

        #if f is not None:
            #try:
                #self.unbind(**{name: f})
            #except KeyError:
                #pass
        
    def property(self, name, quiet=False):
        return None


class State(DictNode):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._appstate_autocreate = False
        self._appstate_autopersist = False
        self._appstate_lazy_watchlist = []
        self._appstate_lazy_kvlang_watchlist = []
        self._appstate_funcwatchlist = defaultdict(list)
        self._appstate_classwatchlist = defaultdict(list)
        #self._appstate_path = 'state'

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
        #print('sig')
        #import ipdb; ipdb.sset_trace()
        #print(path, self._lazy_watchlist, dict(self._classwatchlist))
        path += '.'
        for f, patterns in self._appstate_lazy_kvlang_watchlist:
            module = None
            for pat in patterns:
                self._appstate_funcwatchlist[pat].append((module, f))
                
        for f, patterns in self._appstate_lazy_watchlist:
            module = inspect.getmodule(f)
            #print(f.__qualname__, module, type(f.__qualname__))
            cls = getattr(module, f.__qualname__.split('.')[0])

            if cls and hasattr(cls, f.__name__):
                for pat in patterns:
                    self._appstate_classwatchlist[pat].append((cls, f))
            else:
                for pat in patterns:
                    self._appstate_funcwatchlist[pat].append((module, f))
        self._appstate_lazy_watchlist = []

        for watcher_pat in self._appstate_funcwatchlist:
            watcher = watcher_pat + '.'
            if watcher.startswith(path) or path.startswith(watcher):
                for module, f in self._appstate_funcwatchlist[watcher_pat]:
                    self.call(f)

        for watcher_pat in copy(self._appstate_classwatchlist):
            watcher = watcher_pat + '.'
            if watcher.startswith(path) or path.startswith(watcher):
                for cls, f in self._appstate_classwatchlist[watcher_pat]:
                    name = f.__qualname__.split('.')[-1]
                    for instance in cls._appstate_instances.all():
                        self.call(getattr(instance, name))

    
    def autopersist(self, file, timeout=3, nursery=None):
        self._appstate_shelve = shelve.open(file)
        
        for k, v in self._appstate_shelve.get('state', {}).items():
            self.__setitem__(k, v, signal=False)
        self.signal('state')
        
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


state = State(path='state')
