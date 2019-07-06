# Copyright (c) 2019 Vincent Povirk
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# object model notes
#  all game objects are an instance of BranchingObject
#  subclassing a BranchingObject forks it
#  BranchingObject.fork() also forks it
#  BranchingObject.fork_object identifies the object within its universe
#  BranchingObject.fork_base identifies the universe this object is in (forking creates a universe)
#  BranchingObject does not have a __dict__ but has a world_dictionary
#  world_dictionary keys are (object, name)
#  world_dictionary values should be immutable or a BranchingObject, or they will be unaffected by forks

# TODO:
#  * Make it possible to subclass a BranchingObject instance

class Condition:
    pass

class FrozenDict(dict):
    def __setitem__(self, *args, **kwargs):
        raise TypeError("cannot modify a FrozenDict")
    clear = __setitem__
    pop = __setitem__
    popitem = __setitem__
    setdefault = __setitem__
    update = __setitem__

def _readable_name(x):
    module = ''
    try:
        module = x.__module__ + '.'
    except AttributeError:
        pass
    try:
        qualname = x.__qualname__
    except AttributeError:
        try:
            qualname = x.__name__
        except AttributeError:
            qualname = str(x)
    return module+qualname

_branchingobject_slots = {'fork_base', 'fork_object', 'world_dictionary', 'base_fork_base', 'base_fork_object', 'base_world_dictionary', 'alt_obj_mapping'}

class _NOTHING(object):
    "sentinal value for BranchingObject, nothing to see here"
_NOTHING = _NOTHING()

standard_branching_types = {}

class BranchingObject(object):
    __slots__ = list(_branchingobject_slots)

    def __init__(self, *args, **kwargs):
        self.alt_obj_mapping = None

        # check for special forms
        if 'forked_from' in kwargs:
            base = kwargs['forked_from']
            self.world_dictionary = {}
            self.fork_base = self
            self.fork_object = self
            self.alt_obj_mapping = {}

            # collect universes as fork_base values, and BranchingObject's needing remapped
            alt_bases, alt_objs_set = base._collect_universes()

            if not base.base_world_dictionary or len(base.world_dictionary)**2 >= len(base.base_world_dictionary):
                # make a new base_world_dictionary combining base.base_world_dictionary and base.world_dictionary
                new_base_dictionary = True
                self.base_world_dictionary = {}
                self.base_fork_base = base.fork_base
                self.base_fork_object = base.fork_object
            else:
                # make a new world_dictionary combining base.world_dictionary and other universes
                new_base_dictionary = False
                self.base_world_dictionary = base.base_world_dictionary
                self.base_fork_base = base.base_fork_base
                self.base_fork_object = base.base_fork_object

            # create a clone of each alt-universe object for the new world_dictionary
            for obj in alt_objs_set:
                world_obj = type(obj)(internal_new=True)
                world_obj.base_world_dictionary = self.base_world_dictionary
                world_obj.base_fork_base = self.base_fork_base
                world_obj.base_fork_object = obj
                world_obj.alt_obj_mapping = None
                world_obj.world_dictionary = self.world_dictionary
                world_obj.fork_base = self
                world_obj.fork_object = world_obj
                self.alt_obj_mapping[obj] = world_obj

            # map attributes from the other universes into our world_dictionary
            for alt_base in alt_bases:
                if alt_base.base_world_dictionary:
                    for key, value in alt_base.base_world_dictionary.items():
                        key = translate_from_base(alt_base, key)
                        if key in alt_base.world_dictionary:
                            continue
                        key = translate_from_base(self, key)
                        value = translate_from_base(alt_base, value)
                        value = translate_from_base(self, value)
                        self.world_dictionary[key] = value
                for key, value in alt_base.world_dictionary.items():
                    self.world_dictionary[translate_from_base(self, key)] = translate_from_base(self, value)

            if new_base_dictionary:
                if base.base_world_dictionary:
                    for key, value in base.base_world_dictionary.items():
                        self.base_world_dictionary[translate_from_base(base, key)] = translate_from_base(base, value)
                self.base_world_dictionary.update(base.world_dictionary)
                self.base_world_dictionary = FrozenDict(self.base_world_dictionary)
            else: # new world_dictionary from base's world_dictionary values
                # make a temporary object to translate from base's world to our world
                temp_base = BranchingObject(internal_new=True)
                temp_base.base_world_dictionary = base.world_dictionary
                temp_base.base_fork_base = base.fork_base
                temp_base.base_fork_object = base.fork_object
                temp_base.alt_obj_mapping = self.alt_obj_mapping
                temp_base.world_dictionary = self.world_dictionary
                temp_base.fork_base = self.fork_base
                temp_base.fork_object = self.fork_object
                for key, value in base.world_dictionary.items():
                    self.world_dictionary[translate_from_base(temp_base, key)] = translate_from_base(temp_base, value)

            return

        if 'translate_base' in kwargs and 'translate_gameobject' in kwargs:
            # translate from base universe to current
            base = kwargs['translate_base']
            gameobject = kwargs['translate_gameobject']
            self.world_dictionary = gameobject.world_dictionary
            self.fork_base = gameobject.fork_base
            self.fork_object = base.fork_object
            if base.fork_object is not gameobject.base_fork_object:
                # value is external to base universe
                raise ValueError()
            self.base_world_dictionary = gameobject.base_world_dictionary
            self.base_fork_base = gameobject.fork_base
            self.base_fork_object = base.fork_object

        if 'translate_to_base' in kwargs:
            # make a stub object for the base universe
            obj = kwargs['translate_to_base']
            self.base_world_dictionary = None
            self.base_fork_base = None
            self.base_fork_object = None
            self.world_dictionary = None
            self.fork_base = obj.base_fork_base
            self.fork_object = obj.base_fork_object
            return

        if 'internal_new' in kwargs:
            return

        # no special forms, fall back to generic
        self.base_world_dictionary = None
        self.base_fork_base = None
        self.base_fork_object = None
        self.world_dictionary = {}
        self.fork_base = self
        self.fork_object = self
        self.__ctor__(*args, **kwargs)

    def __collect_universes__(self):
        "find any objects that might be part of a different universe"
        if self.fork_base is not self.fork_object:
            yield self.fork_base
            return
        for key, value in self.world_dictionary.items():
            yield key
            yield value

    def _collect_universes(self):
        "find all related universes to this one"
        bases_stack = []
        iters_stack = []
        seen = {self.fork_base}
        objs = set()
        bases_stack.append(self.fork_base)
        iters_stack.append(self.fork_base.__collect_universes__())
        while bases_stack:
            base = bases_stack[-1]
            it = iters_stack[-1]
            try:
                n = it.__next__()
            except StopIteration:
                bases_stack.pop(-1)
                iters_stack.pop(-1)
            else:
                if n in seen or n in bases_stack:
                    continue
                if isinstance(n, BranchingObject):
                    if n.fork_base is not self.fork_base:
                        objs.add(n)
                    if n.fork_base not in seen:
                        seen.add(n.fork_base)
                        bases_stack.append(n.fork_base)
                        iters_stack.append(n.fork_base.__collect_universes__())
                else:
                    bases_stack.append(n)
                    iters_stack.append(_collect_universes(n))
        seen.remove(self.fork_base)
        return seen, objs

    def __setattr__(self, name, value):
        if name in _branchingobject_slots:
            object.__setattr__(self, name, value)
            return
        try:
            prop = getattr(type(self), name)
        except AttributeError:
            pass
        except TypeError:
            pass
        else:
            try:
                fn = prop.__set__
            except AttributeError:
                pass
            else:
                return fn(self, value)
        value = to_branching_object(value)
        self.__setattr_hook__(name, value, value is _NOTHING)
        self.world_dictionary[self, name] = value

    def __setattr_hook__(self, name, value, delete=False):
        pass

    def __getattribute__(self, name):
        try:
            prop = getattr(type(self), name)
        except AttributeError:
            pass
        except TypeError:
            pass
        else:
            try:
                fn = prop.__get__
            except AttributeError:
                pass
            else:
                return fn(self)
        if name not in _branchingobject_slots:
            try:
                result = self.world_dictionary[self, name]
                if result is _NOTHING:
                    raise AttributeError()
                return result
            except KeyError:
                if self.base_world_dictionary:
                    try:
                        key = translate_to_base(self, (self, name))
                        result = translate_from_base(self, self.base_world_dictionary[key])
                        if result is _NOTHING:
                            raise AttributeError()
                        return result
                    except KeyError:
                        pass
        try:
            return object.__getattribute__(self, name)
        except TypeError:
            raise AttributeError()

    setattr = __setattr__

    def getattr(self, key, *args):
        if len(args) == 0:
            return BranchingObject.__getattribute__(self, key)
        elif len(args) == 1:
            try:
                return self.__getattribute__(key)
            except AttributeError:
                return args[0]
        else:
            raise TypeError("expected at most 2 arguments")

    def hasattr(self, key):
        try:
            self.getattr(key)
        except AttributeError:
            return False
        except TypeError:
            return False
        else:
            return True

    def popattr(self, key):
        result = self.getattr(key)
        self.setattr(key, _NOTHING)
        return result

    __delattr__ = delattr = popattr

    def __hash__(self):
        return id(self.fork_object) + id(self.fork_base)

    def __eq__(self, other):
        if isinstance(other, BranchingObject):
            return id(self.fork_object) == id(other.fork_object) and id(self.fork_base) == id(other.fork_base)
        return False

    def __repr__(self):
        return "<{} object base={:#x} obj={:#x}>".format(_readable_name(type(self)), id(self.fork_base), id(self.fork_object))

    def fork(self):
        """create a copy of this game object and all related objects"""
        return type(self)(forked_from=self)

    def __ctor__(self, *args, **kwargs):
        """override to handle arguments to this type or instances of it"""
        if args:
            raise TypeError("BranchingObject takes no positional arguments")
        for key in kwargs:
            self.setattr(key, kwargs[key])

    def __call__(self, *args, **kwargs):
        result = self.fork()
        result.__ctor__(*args, **kwargs)
        return result

    def __from_base__(self, gameobject):
        if self.fork_object == gameobject.base_fork_base:
            return gameobject.fork_base
        if self.fork_object == gameobject.base_fork_object:
            return gameobject
        if self in gameobject.alt_obj_mapping:
            return gameobject.alt_obj_mapping[self]
        return type(self)(translate_base=self, translate_gameobject=gameobject)

    def __to_base__(self, gameobject):
        if self.base_fork_object is None:
            raise ValueError()
        if self.fork_base == gameobject.fork_base:
            return type(self)(translate_to_base=gameobject)
        else:
            raise ValueError()

def translate_from_base(gameobject, baseobject):
    """translate a key or attribute from the game object's base universe to the forked one

Implement __from_base__(self, gameobject) on the type of object being translated to override.

The default behavior of GameObjectType will create a new instance in the new universe.

Tuples will be translated recursively.

This function may be called more than once for a single object in the base universe.
The result does not have to be identical, but it must be equal and any modifications must be shared.

This raises ValueError if the object was external to the base universe
"""
    try:
        fn = baseobject.__from_base__
    except AttributeError:
        if isinstance(baseobject, tuple):
            return tuple(translate_from_base(gameobject, x) for x in baseobject)
        else:
            return baseobject
    else:
        return fn(gameobject)

def translate_to_base(gameobject, forkedobject):
    """translate a key or attribute from the game object's universe to the base one

Implement __to_base__(self, gameobject) on the type of object being translated to override.

The base universe object must only be used for equality and hashing.

This raises ValueError if the object did not exist in the base universe.
"""
    try:
        fn = forkedobject.__to_base__
    except AttributeError:
        if isinstance(forkedobject, tuple):
            return tuple(translate_to_base(gameobject, x) for x in forkedobject)
        else:
            return forkedobject
    else:
        return fn(gameobject)

def _collect_universes(obj):
    if isinstance(obj, tuple):
        return iter(obj)
    try:
        fn = obj.__collect_universes__
    except AttributeError:
        return iter(())
    else:
        return fn()

def to_branching_object(obj):
    try:
        m = obj.__to_branching_object__
    except AttributeError:
        try:
            f = standard_branching_types[type(obj)]
        except KeyError:
            return obj
        else:
            return f(obj)
    else:
        return m()

def _tuple_to_branching(t):
    result = []
    modified = False
    for item in t:
        new_item = to_branching_object(item)
        result.append(new_item)
        if new_item is not item:
            modified = True
    if modified:
        return tuple(result)
    else:
        return t
standard_branching_types[tuple] = _tuple_to_branching

class BranchingOrderedDictionary(BranchingObject):
    _count = 0

    def __ctor__(self, *args, **kwargs):
        for arg in args:
            self.update(arg)
        for k, v in kwargs.items():
            self[k] = v

    def __cmp__(self, oth):
        raise NotImplementedError()

    def __contains__(self, key):
        return self.hasattr(('_valuefor', key))

    def __delitem__(self, key):
        result = self.popattr(('_valuefor', key))
        try:
            prev = self.popattr(('_prevfor', key))
        except AttributeError:
            # no previous item
            try:
                next = self.popattr(('_nextfor', key))
            except AttributeError:
                # no items left
                assert self._count == 1
                del self._first
                del self._last
            else:
                # old first item
                self._first = next
                self.delattr(('_prevfor', next))
        else:
            # not the first item
            try:
                next = self.popattr(('_nextfor', key))
            except AttributeError:
                # old last item
                self._last = prev
                self.delattr(('_nextfor', prev))
            else:
                # middle item
                self.setattr(('_nextfor', prev), next)
                self.setattr(('_prevfor', next), prev)
        self._count -= 1

    def __getitem__(self, key):
        try:
            return self.getattr(('_valuefor', key))
        except AttributeError:
            raise KeyError()

    def __setitem__(self, key, value):
        if self.hasattr(('_valuefor', key)):
            self.setattr(('_valuefor', key), value)
        else:
            try:
                last = self._last
            except AttributeError:
                self._first = key
                self._last = key
                self.setattr(('_valuefor', key), value)
                self._count += 1
            else:
                self.setattr(('_nextfor', last), key)
                self.setattr(('_prevfor', key), last)
                self._last = key
                self.setattr(('_valuefor', key), value)
                self._count += 1

    def items(self):
        count = self._count
        if count:
            key = self._first
            while True:
                value = self.getattr(('_valuefor', key))
                yield (key, value)
                if self._count != count:
                    raise RuntimeError("dictionary size changed during iteration")
                try:
                    key = self.getattr(('_nextfor', key))
                except AttributeError:
                    break

    def __iter__(self):
        return (k for (k,v) in self.items())

    def __len__(self):
        return self._count

    def clear(self):
        while self._count:
            del self._first

    def copy(self):
        return BranchingOrderedDictonary(self)

    @staticmethod
    def fromkeys(keys, value=None):
        result = BranchingOrderedDictionary
        for key in keys:
            result[key] = value
        return result

    def get(self, key, default=None):
        return self.getattr(('_valuefor', key), default)

    def has_key(self, key):
        return self.hasattr(('_valuefor', key))

    def keys(self):
        return iter(self)

    def pop(self, key):
        result = self[key]
        del self[key]
        return result

    def popitem(self):
        if self._count:
            key = self._first
            value = self.pop(key)
            return key, value
        raise KeyError()

    def setdefault(self, key, value=None):
        try:
            return self[key]
        except KeyError:
            self[key] = value
            return value

    def update(self, arg=None, **kwargs):
        if arg is not None:
            try:
                keys = arg.keys()
            except AttributeError:
                for key, value in arg:
                    self[key] = value
            else:
                for key in keys:
                    self[key] = arg[key]
        for key, value in kwargs.items():
            self[key] = value

    def values(self):
        return (v for (k,v) in self.items())

def _to_branching_dictionary(d):
    result = BranchingOrderedDictionary(d)
    d.clear()
    d[None] = "This dictionary was used with a BranchingObject and automatically converted to a BranchingOrderedDictionary. If you want this object to be branched with others, you should create a BranchingOrderedDictionary. If not, use some other non-branching type."
    return result

standard_branching_types[dict] = _to_branching_dictionary

class GameObjectType(BranchingObject):
    parent = None
    _name = None

    def __ctor__(self, *args, **kwargs):
        self.children = {}
        BranchingObject.__ctor__(self, *args, **kwargs)

    def _get_name(self):
        if self._name is None:
            result = type(self).__name__
            if result.endswith('Type'):
                result = result[:-4]
            self._name = result
        return self._name

    def _set_name(self, name):
        if self.parent is not None:
            raise TypeError("name cannot be changed while a parent exists")
        self._name = name

    name = property(_get_name, _set_name)

    def add_child(self, child, name=None):
        if not isinstance(child, GameObjectType):
            raise TypeError("child must be an instance of GameObjectType")
        if child.parent == self:
            return
        if child.parent is not None:
            child.parent.remove_child(child)
        if name is None:
            name = child.name
        if name in self.children:
            i = 2
            while name + str(i) in self.children:
                i += 1
            name = name + str(i)
        child.name = name
        self.children[name] = child
        child.parent = self

    def remove_child(self, child):
        if not isinstance(child, GameObjectType):
            raise TypeError("child must be an instance of GameObjectType")
        if child.parent != self:
            raise ValueError("remove_child called on non-child")
        del self.children[child.name]
        child.parent = None

    def __setattr_hook__(self, name, value, delete=False):
        BranchingObject.__setattr_hook__(self, name, value, delete)
        if delete:
            value = self.getattr(name)
            if isinstance(value, GameObjectType) and value.parent == self and str(name) == value.name:
                self.remove_child(value)
        elif isinstance(value, GameObjectType) and name != 'parent' and value.parent is None:
            self.add_child(value, str(name))

    def on_choice(self, choice):
        "called when a child Choice has its value set"
        pass

    def debug_print(self, indent=0):
        print(' '*indent+self.name, self)
        for child in self.children.values():
            child.debug_print(indent+2)

GameObject = GameObjectType()

class ChoiceType(GameObjectType):
    """A choice that can be made at configuration time or randomly at seed generation time.

Attributes:
default = The default value for this choice, or None if there is no default. For right now, this has no effect.
known = Boolean indicating whether a value has been selected for this choice.

Properties:
value = The value selected for this choice if set. Accessing this is equivalent to the get_value and set_value methods.

Todo:
Add a concept of a "strategy" which can be used to make this choice randomly at seed generation time.
"""
    default = None

    _value = None
    known = False

    def test_constraints(self, value):
        "Called when set() is called to make sure value is permitted. Raise ValueError if not."
        pass

    def on_set(self, value):
        "Called after a value has been set."
        pass

    def set_value(self, value):
        "Sets this choice's value. This calls the test_constraints and on_set methods on self, and on_choice on the parent object."
        self.test_constraints(value)
        self._value = value
        self.known = True
        self.on_set(value)
        if self.parent is not None:
            self.parent.on_choice(self)

    def get_value(self):
        if not self.known:
            raise ValueError("No value has been set yet")
        return self._value

    value = property(get_value, set_value)

Choice = ChoiceType()

class NumericalChoiceType(ChoiceType):
    """A choice with a numerical value.

Attributes:
maximum = The greaest value this choice can have.
minimum = The lowest value this choice can have.

Todo:
Enforce constraints.
Add possibility to make maximum and minimum exclusive rather than inclusive?"""
    minimum = None
    maximum = None

NumericalChoice = NumericalChoiceType()

class IntegerChoiceType(NumericalChoiceType):
    pass

IntegerChoice = IntegerChoiceType()

class EnumChoiceType(ChoiceType):
    """A choice which must have exactly one out of a pre-determined list of values

Attributes:
values = A tuple of string values. This may be set on the class or an individual choice, but it shouldn't be set for both.
value_names = An optional mapping of string values to human-readable names.
value_descriptions = An optional mapping of string values to descriptions.

TODO: Track known-impossible values? Dependent vertices?"""

EnumChoice = EnumChoiceType()

class WorldType(GameObjectType):
    def __ctor__(self, *args, **kwargs):
        GameObjectType.__ctor__(self, *args, **kwargs)
        self.games = {}

    def add_game(self, child):
        self.add_child(child)
        self.games[child.name] = child

World = WorldType()

class GameType(GameObjectType):
    pass

Game = GameType()

class VertexType(GameObjectType):
    """Anything a player can have or be denied access to. Once a player has access to a vertex, that is permanent and lasts the entire game.

Attributes:
condition = A necessary and sufficient condition to access this vertex. If None, this isn't known yet.
dependent_vertices = A set of vertices which may need to be updated when this one changes.
is_known = A boolean value indicating whether the reachability of this vertex is known for the rest of the game.
known_access = If is_known, whether the vertex is reachable.
necessary_condition = A necessary condition to access this vertex. If this condition is known false, the vertex is known unreachable. This defaults to TrueCondition. For this value to transition from A to B, B must imply A.
sufficient_condition = A sufficient condition to access this vertex. If this condition is known true, the vertex is reachable. This defaults to FalseCondition. For this value to transition from A to B, A must imply B.

TODO: get_referenced_vertices, update_referenced_vertices
deduction functions?
"""


Vertex = VertexType()

class PortType(ChoiceType):
    """A type of object that links a game object to a different game object. Ports work by linking to other ports. Once linked, the parent object will be notified via the on_choice method.

Attributes:
can_self_connect = A boolean value indicating whether this port can be connected to itself.
compatible_types = A tuple of classes of ports to which this port can connect.
chosen_connections = A dictionary of connected ports to the number of connections to that port. Unlike value, this attribute is valid when known is Falseand is expected to be modified after it's initially set.
maximum_connections = The maximum number of ports this port can connect to, including multiple connections to the same port. None for unlimited
maximum_unique_connections = The maximum number of ports this port can connect to, ignoring multiple connections to the same port. None for unlimited.
minimum_connections = The minimum number of ports this port must connect to, including multiple connections to the same port.
minimum_unique_connections = The minimum number of ports this port must connect to, ignoring multiple connections to the same port.
value = A dictionary of connected ports to the number of connections to that port.
"""
    can_self_connect = False
    maximum_connections = 1
    maximum_unique_connections = 1
    minimum_connections = 1
    minimum_unique_connections = 1

    def __ctor__(self, *args, **kwargs):
        ChoiceType.__ctor__(self, *args, **kwargs)
        self.chosen_connections = {}

    def commit(self):
        self.value = self.chosen_connections

    def test_connect(self, other, count=1, test_other=True):
        """Raises ValueError if a connect() call with the same arguments would fail, otherwise does nothing."""
        if count < 0:
            raise ValueError("count cannot be fewer than 0")
        if self.known:
            raise ValueError("This port object can no longer be modified (known == True).")
        if not isinstance(other, self.compatible_types):
            raise ValueError("The other port has an incompatible type")
        if self.maximum_unique_connections is not None:
            new_connections = len(self.chosen_connections) - (1 if other in self.chosen_connections else 0) + (1 if count else 0)
            if new_connections > self.maximum_unique_connections:
                raise ValueError("This would put the number of unique connections above self.maximum_unique_connections")
        if self.maximum_connections is not None:
            new_connections = sum(self.chosen_connections.values()) - (self.chosen_connections.get(other, 0)) + count
            if new_connections > self.maximum_connections:
                raise ValueError("This would put the number of connections above self.maximum_connections")
        if test_other:
            other.test_connect(self, count, False)

    def connect(self, other, count=1):
        """Connect this port to another port.

This will set the total number of connections to 1 (or another count if specified)."""
        self.test_connect(other, count)
        if count == 0:
            del self.chosen_connections[other]
            del other.chosen_connections[self]
        else:
            self.chosen_connections[other] = count
            other.chosen_connections[self] = count

    def multi_connect(self, other, count=1):
        "Add a specific number of connections to another port."
        self.connect(other, self.chosen_connections.get(other, 0)+count)

    def disconnect(self, other, count=None):
        "Remove a connection to another port. If count is set to a number, that many connections will be removed, otherwise all connections will be removed."
        if count is None:
            self.connect(other, count=0)
        else:
            new_count = self.chosen_connections.get(other, 0) - count
            if new_count < 0:
                raise ValueError("A count was specified that is greater than the number of existing connections to the other object.")
            self.connect(other, count=new_count)

    def disconnect_all(self):
        "Remove all connections to other ports."
        while self.chosen_connections:
            for other in self.chosen_connections:
                self.connect(other, count=0)
                break

PortType.compatible_types = (PortType,)

Port = PortType()

class MovementPortType(PortType):
    """A port that allows a player to travel from one position to another.
    
Todo:
can_enter = Condition indicating whether it's possible to enter self.parent through a connected port.
can_exit = Condition indicating whether it's possible to exit self.parent through a connected port.
enter_transitions = List of state transitions and constraints triggered when entering through this port.
exit_transitions = List of state transitions and constraints triggered when exiting through this port.
"""

MovementPortType.compatible_types = (MovementPortType,)

MovementPort = MovementPortType()

class PositionType(GameObjectType):
    '''A place that a player can "be". This could be a room, a door, or a position in space.
Access may be dependent on temporary state like whether a switch has been flipped, so this is not a vertex. Use the access_any_state property or access_with_state method to get a vertex (TODO: implement these).

Attributes:
transient = Boolean value. If True, the player cannot actually *be* here but can pass through here to connect to other areas. An example would be a map screen which can be used in a pause menu to teleport.

Properties:
access_any_state = A vertex indicating that the player can access this position in at least one possible state.
ports = A list of port objects which can be used to exit or enter this position. To modify this list, assign a PortType object as an attribute or using the add_child/remove_child methods.'''

    transient = False

Position = PositionType()

class GridMapType(GameObjectType):
    def __ctor__(self, *args, **kwargs):
        GameObjectType.__ctor__(self, *args, **kwargs)
        self.Width = IntegerChoice(minimum=1, default=10)
        self.Height = IntegerChoice(minimum=1, default=10)

    def new_cell(self, x, y):
        return PositionType(x=x, y=y,
            North=MovementPortType(), South=MovementPortType(),
            East=MovementPortType(), West=MovementPortType())

    def connect_cells_horizontal(self, west, east):
        west.East.disconnect_all()
        east.West.disconnect_all()
        west.East.connect(east.West)

    def connect_cells_vertical(self, north, south):
        north.South.disconnect_all()
        south.North.disconnect_all()
        north.South.connect(south.North)

    def connect_cell_edge(self, cell, name):
        cell.getattr(name).disconnect_all()

    def on_choice(self, choice):
        if (choice in (self.Width, self.Height) and
            self.Width.known and self.Height.known):
            width = self.Width.value
            height = self.Height.value
            x = 0
            while x < width or self.hasattr((x, 0)):
                y = 0
                while y < height or self.hasattr((x, y)):
                    if x < width and y < height:
                        if not self.hasattr((x, y)):
                            self.setattr((x, y), self.new_cell(x, y))
                            if x > 0:
                                self.connect_cells_horizontal(self.getattr((x-1, y)), self.getattr((x, y)))
                            else:
                                self.connect_cell_edge(self.getattr((x, y)), "West")
                            if x == width-1:
                                self.connect_cell_edge(self.getattr((x, y)), "East")
                            if y > 0:
                                self.connect_cells_vertical(self.getattr((x, y-1)), self.getattr((x, y)))
                            else:
                                self.connect_cell_edge(self.getattr((x, y)), "North")
                            if y == height-1:
                                self.connect_cell_edge(self.getattr((x, y)), "South")
                    else:
                        self.delattr((x, y))
                        if x == width and y < height:
                            self.connect_cell_edge(self.getattr((x-1, y)), "East")
                        if y == height and x < width:
                            self.connect_cell_edge(self.getattr((x, y-1)), "South")
                    y += 1
                x += 1

    # TODO: links

GridMap = GridMapType()

# TODO: move maze stuff

class MazeObstacleChoiceType(EnumChoiceType):
    values = ("Nothing", "Wall")
    # TODO: one way north/east, one way south/west, locked, destructable, switch1A,1B,2A,2B,3A,3B

    def __ctor__(self, cell_a, cell_b):
        self.cells = (cell_a, cell_b)

class MazeMap(GridMapType):
    def connect_cells_horizontal(self, west, east):
        GridMapType.connect_cells_horizontal(self, west, east)
        self.setattr('EastObstacle' + str((west.x, west.y)), MazeObstacleChoiceType(west, east))

    def connect_cells_vertical(self, north, south):
        GridMapType.connect_cells_vertical(self, north, south)
        self.setattr('SouthObstacle' + str((north.x, north.y)), MazeObstacleChoiceType(north, south))

    def connect_cell_edge(self, cell, name):
        GridMapType.connect_cell_edge(self, cell, name)
        try:
            self.delattr(name + 'Obstacle' + str((cell.x, cell.y)))
        except AttributeError:
            pass

class MazeGame(GameType):
    def __ctor__(self, *args, **kwargs):
        GameType.__ctor__(self, *args, **kwargs)
        self.map = MazeMap()

# TODO: move tests
if __name__ == '__main__':
    obj = GameObjectType(sdf=2)
    obj2 = obj.fork()
    obj2.jkl = 3
    obj.qwe = 4
    obj3 = obj2.fork()
    obj3.zxc = 5
    obj4 = obj.fork()
    obj4.qwe = 6
    assert obj2.sdf == 2
    assert obj2.jkl == 3
    assert obj.qwe == 4
    assert not hasattr(obj2, 'qwe')
    assert not hasattr(obj, 'jkl')
    assert obj3.sdf == 2
    assert obj3.jkl == 3
    assert obj3.zxc == 5
    assert obj4.sdf == 2
    assert obj4.qwe == 6

    assert Choice.default == None
    choice = Choice(default = 5)
    assert choice.default == 5
    choice = ChoiceType(default = 6)
    assert choice.default == 6
    choice = ChoiceType()
    assert choice.default == None

    world = World()
    game1 = Game(huh = 1)
    game2 = Game()
    world.add_game(game1)
    world.add_game(game2)
    assert game1.name == 'Game'
    assert game2.name == 'Game2'
    assert game1 in world.games.values()
    assert game2 in world.games.values()
    assert world.games['Game'].huh == 1

    world2 = world.fork()
    assert world2.games['Game'].huh == 1
    assert world2.games['Game'] != game1
    assert world2.games['Game'] == world2.games['Game']
    world2.games['Game'].huh = 2
    assert world2.games['Game'].huh == 2
    assert game1.huh == 1

    d1 = BranchingOrderedDictionary()
    assert len(d1) == 0
    d1[1] = 2
    assert d1[1] == 2
    d2 = d1.fork()
    assert d2[1] == 2
    d2[2] = 4
    assert list(d2.items()) == [(1, 2), (2, 4)]

    d2[3] = 6
    d2[4] = 8
    assert list(d2.items()) == [(1, 2), (2, 4), (3, 6), (4, 8)]

    del d2[2]
    assert list(d2.items()) == [(1, 2), (3, 6), (4, 8)]

    del d2[1]
    assert list(d2.items()) == [(3, 6), (4, 8)]

    del d2[4]
    assert list(d2.items()) == [(3, 6)]

    del d2[3]
    assert list(d2.items()) == []
    assert not d2

    # MazeGame tests
    world = World()
    maze = MazeGame()
    world.add_game(maze)
    assert('(0, 0)' not in maze.map.children)

    maze.map.Width.set_value(3)
    maze.map.Height.set_value(4)
    assert('(0, 0)' in maze.map.children)
    assert('(2, 3)' in maze.map.children)

    maze.map.Width.value = 5
    maze.map.Height.value = 2
    assert('(2, 1)' in maze.map.children)
    assert('(1, 2)' not in maze.map.children)

    maze.map.Width.value = 2
    maze.map.Height.set_value(5)
    assert('(2, 1)' not in maze.map.children)
    assert('(1, 2)' in maze.map.children)
