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

import hashlib
import random

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

class _NOTHING(object):
    "sentinal value for BranchingObject, nothing to see here"
_NOTHING = _NOTHING()

class Universe:
    __slots__ = ['dictionary', 'dictionary_is_readonly', 'readonly', 'related_universes', 'base_universes', 'object_to_base', 'base_to_object']

    def __init__(self, readonly_copy_of=None, base_universes=None):
        if readonly_copy_of is not None:
            self.dictionary = readonly_copy_of.dictionary
            self.dictionary_is_readonly = True
            self.readonly = True
            self.related_universes = None
            self.base_universes = readonly_copy_of.base_universes
            self.object_to_base = readonly_copy_of.object_to_base.copy()
            self.base_to_object = readonly_copy_of.base_to_object.copy()
        elif base_universes is not None:
            self.dictionary = {}
            self.dictionary_is_readonly = False
            self.readonly = False
            self.related_universes = {self}
            self.base_universes = base_universes
            self.object_to_base = {}
            self.base_to_object = {}
        else:
            self.dictionary = {}
            self.dictionary_is_readonly = False
            self.readonly = False
            self.related_universes = {self}
            self.base_universes = {} # mapping of original base universes to read-only copies
            self.object_to_base = {}
            self.base_to_object = {}

    def combine_universes(self, value):
        "add value's universe to related_universes"
        if isinstance(value, BranchingObject):
            if value.__universe__.related_universes is not self.related_universes:
                if len(value.__universe__.related_universes) > len(self.related_universes):
                    greater = value.__universe__.related_universes
                    lesser = self.related_universes
                else:
                    greater = self.related_universes
                    lesser = value.__universe__.related_universes
                greater.update(lesser)
                for universe in lesser:
                    universe.related_universes = greater
        elif isinstance(value, tuple):
            for item in value:
                self.combine_universes(item)
        else:
            try:
                value.__combine_universes__(self)
            except AttributeError:
                pass

    def translate_to_base(self, obj):
        if isinstance(obj, BranchingObject):
            return self.object_to_base[obj][0]
        elif isinstance(obj, tuple):
            return tuple(self.translate_to_base(x) for x in obj)
        else:
            try:
                return obj.__translate_to_base__(self)
            except AttributeError:
                return obj

    def translate_from_base(self, obj):
        if isinstance(obj, BranchingObject):
            try:
                return self.base_to_object[obj]
            except KeyError:
                self.base_to_object[obj] = result = type(obj).__new__(type(obj))
                object.__setattr__(result, '__universe__', self)
                self.object_to_base[result] = obj, self.base_universes[object.__getattribute__(obj, '__universe__')]
                return result
        elif isinstance(obj, tuple):
            return tuple(self.translate_from_base(x) for x in obj)
        else:
            try:
                return obj.__translate_from_base__(self)
            except AttributeError:
                return obj

    def setattr(self, obj, key, value):
        if self.readonly:
            raise ValueError("Universe is readonly")
        if self.dictionary_is_readonly:
            self.dictionary = self.dictionary.copy()
            self.dictionary_is_readonly = False
        self.dictionary[obj, key] = value
        self.combine_universes(key)
        self.combine_universes(value)

    def getattr(self, obj, key):
        try:
            result = self.dictionary[obj, key]
        except KeyError:
            pass
        else:
            return result

        try:
            base_obj, base_universe = self.object_to_base[obj]
            base_key = self.translate_to_base(key)
        except KeyError:
            pass
        else:
            try:
                result = base_universe.getattr(base_obj, base_key)
            except AttributeError:
                pass
            else:
                return self.translate_from_base(result)

        raise AttributeError()

    def readonly_copy(self):
        if self.readonly:
            return self
        self.dictionary_is_readonly = True
        return Universe(readonly_copy_of=self)

    def fork(self):
        # make a readonly copy of every related universe
        base_universes = {}
        for universe in self.related_universes:
            base_universes[universe] = universe.readonly_copy()
        return Universe(base_universes=base_universes)

    def debug_dump(self, indent='', parent=None):
        objects = set()
        objects.update(self.object_to_base.keys())
        for k in self.dictionary.keys():
            objects.add(k[0])
        print(indent+'Objects:')
        for obj in objects:
            print(indent+'  '+repr(obj))
            if obj in self.object_to_base:
                print(indent+'    To base:', self.object_to_base[obj][0], self.object_to_base[obj][1])
            if parent is not None and obj in parent.base_to_object:
                print(indent+'    From base:', parent.base_to_object[obj])
            for k, v in self.dictionary.items():
                if k[0] != obj:
                    continue
                print(indent+'    '+repr(k[1]), '=', repr(v))
        if self.base_universes:
            print(indent+'Bases:')
            for k, v in self.base_universes.items():
                print(indent+'  '+repr(k), repr(v))
                v.debug_dump(indent+'  ', self)
                

standard_branching_types = {}

class BranchingObject(object):
    __slots__ = ['__universe__']

    def __init__(self, *args, **kwargs):
        object.__setattr__(self, '__universe__', Universe()) # FIXME: Use a metaclass to put this in __call__ ?
        self.__ctor__(*args, **kwargs)

    def __setattr__(self, name, value):
        if name == '__universe__':
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
        object.__getattribute__(self, '__universe__').setattr(self, name, value)

    def __setattr_hook__(self, name, value, delete=False):
        pass

    def __getattribute__(self, name):
        if name == '__universe__':
            return object.__getattribute__(self, name)
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
        try:
            result = object.__getattribute__(self, '__universe__').getattr(self, name)
        except AttributeError:
            pass
        else:
            if result is _NOTHING:
                raise AttributeError()
            return result
        try:
            return object.__getattribute__(self, name)
        except TypeError:
            pass
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

    def fork(self):
        """create a copy of this object and all related objects"""
        universe = object.__getattribute__(self, '__universe__')
        new_universe = universe.fork()
        return new_universe.translate_from_base(self)

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
    _path = None

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

    def _get_path(self):
        if self._path is None:
            if self.parent is None:
                self._path = (self.name,)
            else:
                self._path = self.parent.path + (self.name,)
        return self._path

    path = property(_get_path)

    def object_from_path(self, path, relative=False):
        if relative:
            pos = 0
            parent = self
        else:
            # find root
            pos = 1
            obj = self
            parent = None
            while obj is not None:
                if obj.name == path[0]:
                    parent = obj
                obj = obj.parent
            if parent is None:
                raise ValueError("Could not find root object %r" % path[0])
        while pos < len(path):
            parent = parent.children[path[pos]]
            pos += 1
        return parent

    def get_string_path(self):
        return '.'.join(self.path)

    def __repr__(self):
        if self._name is None:
            # avoid side-effects from accessing self.name
            return BranchingObject.__repr__(self)
        return "<%s object at %s in universe 0x%x>" % (type(self).__name__, self.get_string_path(), id(self.__universe__))

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
        child._path = None

    def remove_child(self, child):
        if not isinstance(child, GameObjectType):
            raise TypeError("child must be an instance of GameObjectType")
        if child.parent != self:
            raise ValueError("remove_child called on non-child")
        del self.children[child.name]
        child.parent = None
        child._path = None

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

    def get_world(self):
        obj = self
        while not isinstance(obj, WorldType):
            obj = obj.parent
        return obj

    def mark_fast_deduction(self):
        "Indicates that fast_deduce() should be called on this object"
        world = self.get_world()
        if world is not None:
            world.fast_deduction_objects[self] = True

    def fast_deduce(self):
        """Called during generation. Objects should make checks to find contradictions or eliminate choices provided they:
1. Are completable in O(1) time. (This may result in calls to mark_fast_deduction and thus further calls to fast_deduce. Overall, this should be completable in linear time based on the number of objects involved.)
2. Have a good chance of finding impossible choices early. As choices are attempted, the fast deductions should be exploring the immediate consequences.

This can be used for tasks that are required to generate the world, such as determining the conditions for reaching a vertex based on some choice once it's been made.

This method may raise LogicError."""
        pass

    def debug_print(self, indent=0):
        print(' '*indent+self.name, self)
        for child in self.children.values():
            child.debug_print(indent+2)

GameObject = GameObjectType()

class LogicError(Exception):
    """Indicates that the current game state has an error, such as a contradiction, or an unreachable goal.

This must only be raised from certain expected methods, such as GameObject.fast_deduce."""

class ChoiceStrategy(BranchingObject):
    """A method for making a choice, randomly or otherwise"""

    def __init__(self):
        if type(self) == ChoiceStrategy:
            raise TypeError("ChoiceStrategy is an abstract class")

    def make_choice(self, choice):
        """Makes the choice. Multiple iterations may be required before choice.value is known.

This modifies choice and returns a token which can be passed to eliminate_choice.

This must be overridden by subclasses, and does not need to be called by them."""
        if type(self).make_choice == ChoiceStrategy.make_choice:
            raise TypeError("ChoiceStrategy.make_choice must be overridden by subclasses")

    def eliminate_choice(self, choice, token):
        """Called with a token from make_choice when the choice leads to a contradiction. This modifies the choice object, or related objects, to prevent the same choice from being made and potentially allow deductions to be made.

This must be overridden by subclasses, and does not need to be called by them."""
        if type(self).eliminate_choice == ChoiceStrategy.eliminate_choice:
            raise TypeError("ChoiceStrategy.eliminate_choice must be overridden by subclasses")    

class ChoiceType(GameObjectType):
    """A choice that can be made at configuration time or randomly at seed generation time.

Either default, strategy, or value must be set for all choice objects.

Attributes:
default = The default value for this choice, or None if there is no default.
strategy = The strategy used to make this choice.
known = Boolean indicating whether a value has been selected for this choice.

Properties:
value = The value selected for this choice if set. Accessing this is equivalent to the get_value and set_value methods.
"""
    default = None
    strategy = None

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

    def make(self):
        if self.known:
            return
        if self.strategy is not None:
            return self.strategy.make_choice(self)
        if self.default is not None:
            self.set_value(self.default)
        raise ValueError("%r must have a value, strategy, or default before make() is called." % self)
    
    def eliminate(self, token):
        if self.strategy is None:
            # FIXME: We probably should handle defaults in fast_deduce instead.
            raise LogicError("%r has no strategy, and the default or assigned value led to a contradiction." % self)
        self.strategy.eliminate_choice(self, token)

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

class ContradictionException(Exception):
    pass

class RandomFactory:
    def __init__(self, seed=None):
        if seed is None:
            r = random.SystemRandom()
            seed = bytes(r.randint(0,255) for i in range(16))

        if isinstance(seed, str):
            seed = seed.encode('utf8')

        self.seed = seed

    def __call__(self, data):
        if isinstance(data, str):
            data = data.encode('utf8')

        md5 = hashlib.new('md5')

        md5.update(data)
        md5.update(self.seed)

        seed = int(md5.hexdigest(), 16) # this seems inefficient but is it worse than a loop in python?

        return random.Random(seed)

class WorldType(GameObjectType):
    def __ctor__(self, *args, **kwargs):
        GameObjectType.__ctor__(self, *args, **kwargs)
        self.games = {}
        self.fast_deduction_objects = {}

    def add_game(self, child):
        self.add_child(child)
        self.games[child.name] = child

    def deduce(self):
        # TODO: expensive deductions, at random, and boost probability if they are fruitful?

        while self.fast_deduction_objects:
            obj, _ = self.fast_deduction_objects.popitem()
            obj.fast_deduce()

    def generate(self, seed=None):
        self.rng = RandomFactory(seed)

        world = self.fork()

        # Mark all objects as requiring deduction
        object_queue = [world]
        while object_queue:
            obj = object_queue.pop()
            obj.mark_fast_deduction()
            for child in obj.children.values():
                object_queue.append(child)

        # Make deductions
        world.deduce()

        choices = []
        choices_made = []

        while True:
            # Collect all choices and sort randomly
            if not choices:
                object_queue = [world]
                while object_queue:
                    obj = object_queue.pop()
                    if isinstance(obj, ChoiceType) and not obj.known:
                        choices.append(obj.path)
                    for child in obj.children.values():
                        object_queue.append(child)
                choices.sort(key=lambda x: self.rng('.'.join(x)+'choice_order').random())
                if not choices:
                    break

            while choices:
                choice_path = choices.pop()

                choice = world.object_from_path(choice_path)

                saved_state = world.fork() # this does not invalidate our choice object

                token = choice.make()

                choices_made.push((saved_state, choice_path, token))

                while True:
                    try:
                        world.deduce()
                    except LogicError:
                        raise Exception("TODO: implement backtracking")
                        #   + restore state and mark that the choice made is not possible
                        #   + make deductions
                        #   + while contradiction
                        #     - boost probability of any expensive deductions involved, AND the choice we attempted to make
                        #     - binary search to find the most recent state that holds up given the specific set of expensive deductions
                        #     - mark the recent state's corresponding choice as not possible
                    else:
                        break

                raise NotImplementedError() # to prevent infinite loop for now


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
        EnumChoiceType.__ctor__(self)
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

    # test generation
    maze.map.Width.value = 10
    maze.map.Height.value = 10

    world.generate('test seed')
