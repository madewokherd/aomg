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
#  * Make it possible to use a dict in GameObject
#   * dictionaries should be automatically converted on assignment
#   * BranchingObject instances need a prototype to hold class attributes
#  * Use a dict in GameObject for children
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
        self.world_dictionary[self, name] = value

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

GameObject = GameObjectType()

class ChoiceType(GameObjectType):
    default = None

Choice = ChoiceType()

class NumericalChoiceType(ChoiceType):
    minimum = None
    maximum = None

NumericalChoice = NumericalChoiceType()

class IntegerChoiceType(NumericalChoiceType):
    pass

IntegerChoice = IntegerChoiceType()

class WorldType(GameObjectType):
    def __ctor__(self):
        GameObjectType.__ctor__(self)
        self.games = {}

    def add_game(self, child):
        self.add_child(child)
        self.games[child.name] = child

World = WorldType()

class GameType(GameObjectType):
    pass

Game = GameType()



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

"""first attempt

class MazeGame(Game):
    # TODO: Move this to another module
    Width = IntegerChoice(min=1, default=10)
    Height = IntegerChoice(min=1, default=10)

# TODO: Move this
if __name__ == '__main__':
    def print_tree(x, depth=0):
        print("%s%s" % (' '*depth, x.name))
        for child in x:
            print_tree(child, depth+1)

    print_tree(World)
    print_tree(MazeGame)

    world = World()
    maze = MazeGame()
    world.add_game(maze)
    print_tree(world)
"""
