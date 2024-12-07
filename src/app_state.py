import asyncio
import inspect
import logging
import shelve
from collections import defaultdict, UserDict
from collections.abc import Mapping
from copy import copy
from functools import update_wrapper, partial
from collections.abc import Callable, Generator, Coroutine
from pathlib import Path
from textwrap import shorten

try:
    import kivy.event
except:
    kivy = False

try:
    import trio
except ImportError:
    pass

from getinstance import InstanceManager
from lockorator.asyncio import lock_or_exit
from sniffio import current_async_library


logger = logging.getLogger(__name__)


if kivy:
    class BaseDict(kivy.event.Observable, UserDict):
        """
        Provides fbind() method which lets kivy.lang.Builder to
        listen to state changes.
        """

        def property(self, name, quiet=False):
            """ kivy builder requires this method. """
            return None

        # def __reduce__(self):
        #     """ Persist as a regular dict """
        #     return (dict, (self.data,))

        def fbind(self, name, func, args, **kwargs):
            """ Called by kivy lang builder to bind state node. """
            element, key, value, rule, idmap = args
            logger.debug(f"kivy called fbind {self._appstate_path}.{name} {rule=}")

            @on(f"{self._appstate_path}.{name}")
            def notify_kivy():
                # logger.debug(f"Calling {self._appstate_path}.{name}")
                func(args, None, None)

else:
    BaseDict = UserDict


class DictNode(BaseDict):
    def __init__(self, *args, path, **kwargs):
        self._appstate_path = path

        self.data = {}

        if args:
            self.update(args[0], signal=False)
        if kwargs:
            self.update(kwargs, signal=False)

    def __repr__(self):
        return repr(self.as_dict(full=True))

    def __str__(self):
        return str(self.data) if self.data else ''

    def _make_subnode(self, key, value):
        # logger.debug(f'make {self._appstate_path}.{key} {value=} {type(value)=}')
        if isinstance(value, DictNode):
            # logger.debug(f'  already DictNode')
            return value
        if not isinstance(value, Mapping):
            return value

        return DictNode(value, path=f'{self._appstate_path}.{key}')

    def __getitem__(self, name):
        # logger.debug(f'__getitem__ {self._appstate_path}.{name}')
        return self._make_subnode(name, super().__getitem__(name))

    def get(self, key, *args, **kwargs):
        # logger.debug(f'get {self._appstate_path}.{key}')
        return self._make_subnode(key, super().get(key, *args, **kwargs))

    def __getattribute__(self, name):
        # logger.debug(f'__getattribute__ {name}')
        if name.startswith('_') or name == 'data' or name in DictNode.__dict__  or name in dict.__dict__:
            # logger.debug(f'__getattribute__ {name} direct')
            return super().__getattribute__(name)

        # logger.debug(f'__getattribute__ {name}')
        try:
            result = self[name]
        except KeyError:
            try:
                return super().__getattribute__(name)
            except:
                # Support access of non-existent chain of keys:
                # >>> assert state.some.node.which.dont.exist == {}

                # Questionable feature, but simplifies some cases
                # especially with the limited kvlang syntax.
                return self._make_subnode(name, {})

        if isinstance(result, list):
            result = [self._make_subnode('_list', x) for x in result]

        return result

    def __delitem__(self, key):
        super().__delitem__(key)
        on.trigger(f'{self._appstate_path}.{key}')

    def update(self, *a, signal=True, **kw):
        # logger.debug(f'update {a}, {kw}')

        changed = False
        if len(a) > 1:
            raise TypeError(f'update expected at most 1 arguments, got {len(a)}')
        if a:
            if hasattr(a[0], 'keys'):
                for key in a[0]:
                    if key not in self or not self[key] == a[0][key]:
                        # logger.debug(f'update {key} {a[0][key]}')
                        changed = True
                        #logger.debug(key, a[0][key])
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

        if changed and signal:
            on.trigger(f'{self._appstate_path}')
            # logger.debug(f'UPDATE: changed {self._appstate_path}')
        # else:
        #     logger.debug(f'Not changed {self._appstate_path}')


    def setdefault(self, key, value):
        if key not in self:
            self[key] = value
        return self[key]

    def __setitem__(self, key, value, signal=True):
        # logger.debug(f'  __setitem__ {self._appstate_path}[{key}] = {value}')

        if '_list' in self._appstate_path.split('.'):
            node = self._make_subnode(key, value)
            return super().__setitem__(key, node)

        ancestor = state
        for path in self._appstate_path.split('.')[1:-1]:
            # For each my ancestor, ensure it existis in state. Create new
            # empty node if not.

            # logger.debug(f"{ancestor._appstate_path=} {path=}")
            if path in ancestor:
                # logger.debug(f'!!     {path} is already in {ancestor._appstate_path}')
                if isinstance(ancestor[path], DictNode):
                    # logger.debug(f'already exists {ancestor._appstate_path}.{path} ')
                    ancestor = ancestor[path]
                    continue
                # else:
                    # logger.debug(f"{path} exists but it's not a dict node")

            # logger.debug(f'setting {ancestor._appstate_path}.{path} = {{}}')
            ancestor.__setitem__(path, ancestor._make_subnode(path, {}), signal=False)
            ancestor = ancestor[path]

        my_name = self._appstate_path.split('.')[-1]
        if not my_name == 'state':
            # I am not the root (self != state). Ensure that ancestor contains myself
            ancestor.__setitem__(my_name, self, signal=False)

        # Finally, create node from given value
        super().__setitem__(key, self._make_subnode(key, value))

        if signal:
            on.trigger(f'{self._appstate_path}.{key}')


    def __setattr__(self, name, value):
        if name.startswith('_appstate_') or name == 'data':
            return super().__setattr__(name, value)

        # logger.debug(f'__setattr__ {self._appstate_path}.{name} = {value}')
        node = self._make_subnode(name, value)

        if name.startswith('_'):
            super().__setattr__(name, node)
            on.trigger(f'{self._appstate_path}.{name}')
            #logger.debug(f'signal {self._appstate_path}.{name}')
        else:
            self.__setitem__(name, node)
        # logger.debug(f'END __setattr__ {self._appstate_path}.{name} = {value}')


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
    """
    Root node, singleton.
    """

    def reset(self):
        for key in list(self.keys()):
            super().__delitem__(key)


    def autopersist(self, filename: str | Path, timeout=3, nursery=None):
        self._appstate_shelve = shelve.open(str(filename))

        # logger.debug(f'Starting autopersist')

        for k, v in self._appstate_shelve.get('state', {}).items():
            # logger.debug(f'loading from storage {k=} {v=}')
            self.__setitem__(k, v, signal=False)

        # logger.debug(f'Finished loading from storage')
        on.trigger('state')

        @on('state')
        def persist():
            if timeout == 0:
                logger.debug('Saving state:\n{items}'.format(items="\n".join(
                    f'{key}: {shorten(str(value), 60)}' for key, value in state.items()
                )))
                state._appstate_shelve['state'] = state.as_dict()
                state._appstate_shelve.sync()
                return

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


    def reload(self, filename: str | Path):
        if self._appstate_shelve:
            self._appstate_shelve.close()

        self._appstate_shelve = shelve.open(str(filename))

        # logger.debug(f'Starting reload')

        for k, v in self._appstate_shelve.get('state', {}).items():
            # logger.debug(f'loading from storage {k=} {v=}')
            self.__setitem__(k, v, signal=False)

        # logger.debug(f'Finished loading from storage')
        on.trigger('state')


@lock_or_exit()
async def persist_delayed(timeout):
    logger.debug('Saving state:\n{items}'.format(items="\n".join(
        f'{key}: {shorten(str(value), 60)}' for key, value in state.items()
    )))
    if current_async_library() == 'trio':
        await trio.sleep(timeout)
    else:
        await asyncio.sleep(timeout)
    #logger.debug('PERSIST', state)
    state._appstate_shelve['state'] = state.as_dict()
    state._appstate_shelve.sync()


def maybe_async(callable: Coroutine | Callable):
    """
    Execute sync callable, or schedule async task.
    """
    if not inspect.iscoroutinefunction(callable):
        return callable()

    if current_async_library() == 'trio':
        if not getattr(state, '_nursery'):
            raise Exception('Provide state._nursery for async task to run.')
        state._nursery.start_soon(callable)
    else:
        return asyncio.create_task(callable())


class signal_handler:
    """
    Decorator of a function or method. Pass-through calls to the wrapped callable.
    Only used internally by the @on('state.foo') decorator, defined below.

    Provides deliver() method to be called by on.trigger() when state changes.

    If wrapped callable is a method, __set_name__() ensures that owner class
    has a member `_appstate_instances` which is an getinstance.InstanceManager.
    When the state changes, deliver() calls the method for each instance of the
    owner class.

    """

    def __init__(self, callable: Callable):
        self.callable = callable
        self.owner_class = None
        update_wrapper(self, callable)

    def __call__(self, *a, **kw):
        return self.callable(*a, **kw)

    def __set_name__(self, owner: type, name: str):
        """
        Called when (if) this callable is assigned as a method of a class.
        If that class (owner) does not have `_appstate_instances` member, then
        create it.
        """
        if not hasattr(owner, '_appstate_instances'):
            owner._appstate_instances = InstanceManager(owner, '_appstate_instances')

        setattr(owner, self.callable.__name__, self.callable)
        self.owner_class = owner

    def deliver(self):
        """
        Called by on.trigger() when state changes. Execute wrapped callable
        or call a method of all owner class instances. If async, schedule
        a task.
        """
        if self.owner_class:
            # Call method of every existing instance of an owner class.
            for instance in self.owner_class._appstate_instances.all():
                maybe_async(getattr(instance, self.callable.__name__))
        else:
            maybe_async(self.callable)


class on:
    """
    Decorator of a function or method. Decorated callable is converted
    into signal_handler(), defined above. This signal handler will be
    triggered each time when state node matching any of the provided
    state path patterns changes.

    Usage:

        @on('state.username', 'state.something_else')
        def on_username_changed():
            print(f"New username = {state.username}")

    """

    # Watchlist mapping 'state.foo.' -> list of callables
    handlers: dict[str, list[signal_handler]] = defaultdict(list)

    def __init__(self, *patterns: str):
        """ Set state path patterns to react on. """
        self.patterns = patterns


    def __call__(self, callable: Callable) -> signal_handler:
        """
        Decorate the given callable, converting it into signal_handler.

        If callable is a class method, signal_handler ensures owner class has
        `_appstate_instances = getinstance.InstanceManager()`. This
        instance manager will be required to call the method of every
        class instance upon the state change.

        Add this signal handler to the watchlist to react on state
        changes with given state path patterns.
        """
        handler = signal_handler(callable)

        for pattern in self.patterns:
            # Ensure path pattern ends with a dot. Enables simple
            # substring path matching in on.match(), distinguishing
            # state.foo from state.foobar
            on.handlers[pattern + '.'].append(handler)

        return handler


    @staticmethod
    def trigger(path: str) -> None:
        """
        Execute all signal handlers that match given path pattern.

        Called by DictNode when it is changed. Parameter `path` is changed node's
        _appstate_path. For ex: "state.countries.au"
        """
        for handler in on.match(path + '.'):
            handler.deliver()

    @staticmethod
    def match(path: str) -> Generator[signal_handler]:
        """
        Yield all signal_handlers that match given path pattern.
        Called by on.trigger().
        """
        for pattern in list(on.handlers):
            if pattern.startswith(path):
                # state.foo.bar. handler triggered by change of state.foo.
                yield from on.handlers[pattern]
            elif path.startswith(pattern):
                # state.foo. handler triggered by change of state.foo.bar.
                yield from on.handlers[pattern]


state = State(path='state')
