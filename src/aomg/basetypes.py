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
#  all game objects are an instance of _GameObjectType
#  _GameObjectType is not a subclass of type
#  _GameObjectType can be subclassed
#  subclassing a GameObject forks it
#  GameObject.fork() also forks it
#  GameObject.fork_object identifies the object within its universe
#  GameObject.fork_base identifies the universe this object is in (forking creates a universe)
#  GameObject does not have a __dict__ but has a world_dictionary
#  world_dictionary keys are (object, name)
#  world_dictionary values must be immutable or a GameObject
#  GameObjects will typically have a name and a parent, but these are not special

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

_gameobject_slots = {'fork_base', 'fork_object', 'world_dictionary', 'base_fork_base', 'base_fork_object', 'base_world_dictionary'}

class GameObjectType(object):
    __slots__ = list(_gameobject_slots)

    children = ()
    parent = None

    def __init__(self, *args, **kwargs):
        # check for special forms
        if 'forked_from' in kwargs:
            base = kwargs['forked_from']
            self.world_dictionary = {}
            self.fork_base = self
            self.fork_object = self
            if not base.base_world_dictionary or len(base.world_dictionary)**2 >= len(base.base_world_dictionary):
                base_dict = {}
                self.base_fork_base = base.fork_base
                self.base_fork_object = base.fork_object
                if base.base_world_dictionary:
                    for key, value in base.base_world_dictionary.items():
                        base_dict[translate_from_base(base, key)] = translate_from_base(base, value)
                base_dict.update(base.world_dictionary)
                self.base_world_dictionary = FrozenDict(base_dict)
            else:
                self.base_world_dictionary = base.base_world_dictionary
                self.base_fork_base = base.base_fork_base
                self.base_fork_object = base.base_fork_object
                for key, value in base.world_dictionary.items():
                    self.world_dictionary[translate_from_base(self, key)] = translate_from_base(self, value)
            return

        if 'translate_base' in kwargs and 'translate_gameobject' in kwargs:
            base = kwargs['translate_base']
            gameobject = kwargs['translate_gameobject']
            self.world_dictionary = gameobject.world_dictionary
            self.fork_base = gameobject.fork_base
            self.fork_object = base.fork_object
            if base.fork_object == gameobject.base_fork_object:
                # this object comes from the game's base universe, just make a stub
                self.base_world_dictionary = gameobject.base_world_dictionary
                self.base_fork_base = gameobject.fork_base
                self.base_fork_object = base.fork_object
            elif (base.fork_base, '_combined_universe') in self.world_dictionary:
                # these objects come from different universes, but we already combined them
                self.base_world_dictionary = gameobject.base_world_dictionary
                self.base_fork_base = gameobject.fork_base
                self.base_fork_object = base.fork_object
            else:
                # different universe, bring all its attributes into this one
                base_dictionary = {}
                base_dictionary.update(base.world_dictionary)
                for (key, value) in base.base_world_dictionary.items():
                    base_dictionary[translate_from_base(base, key)] = translate_from_base(base, value)

                # set base attributes temporarily to translate the base_dictionary values
                self.base_world_dictionary = base.world_dictionary
                self.base_fork_base = base.fork_base
                self.base_fork_object = base.fork_object
                self.world_dictionary[base.fork_base, '_combined_universe'] = True

                # translate base_dictionary values into world_dictionary
                for (key, value) in base_dictionary.items():
                    self.world_dictionary[translate_from_base(self, key)] = translate_from_base(self, value)

                # set final base attributes
                self.base_world_dictionary = gameobject.base_world_dictionary
                self.base_fork_base = gameobject.fork_base
                self.base_fork_object = base.fork_object
            return

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

        # no special forms, fall back to generic
        self.base_world_dictionary = None
        self.base_fork_base = None
        self.base_fork_object = None
        self.world_dictionary = {}
        self.fork_base = self
        self.fork_object = self
        self.__ctor__(*args, **kwargs)

    def __setattr__(self, name, value):
        if name in _gameobject_slots:
            object.__setattr__(self, name, value)
            return
        self.world_dictionary[self, name] = value

    def __getattribute__(self, name):
        try:
            prop = getattr(type(self), name)
            fn = prop.__get__
        except AttributeError:
            pass
        else:
            return fn(self)
        if name not in _gameobject_slots:
            try:
                return self.world_dictionary[self, name]
            except KeyError:
                if self.base_world_dictionary:
                    try:
                        key = translate_to_base(self, (self, name))
                        return translate_from_base(self, self.base_world_dictionary[key])
                    except KeyError:
                        pass
        return object.__getattribute__(self, name)

    def __hash__(self):
        return id(self.fork_object) + id(self.fork_base)

    def __eq__(self, other):
        if isinstance(other, GameObjectType):
            return id(self.fork_object) == id(other.fork_object) and id(self.fork_base) == id(other.fork_base)
        return False

    def fork(self):
        """create a copy of this game object and all related objects"""
        return type(self)(forked_from=self)

    def __ctor__(self, *args, **kwargs):
        """override to handle arguments to this type or instances of it"""
        if args:
            raise TypeError("GameObjectType takes no positional arguments")
        for key in kwargs:
            setattr(self, key, kwargs[key])

    def __call__(self, *args, **kwargs):
        result = self.fork()
        result.__ctor__(*args, **kwargs)
        return result

    def add_child(self, child):
        if child.parent == self:
            return
        if child.parent != None:
            child.parent.remove_child(child)
        self.children = self.children + (child,)
        child.parent = self

    def __from_base__(self, gameobject):
        if self.fork_object == gameobject.base_fork_object:
            return gameobject
        return type(self)(translate_base=self, translate_gameobject=gameobject)

    def __to_base__(self, gameobject):
        if self.base_fork_object is None:
            raise ValueError()
        if self.fork_base == gameobject.fork_base:
            return type(self)(translate_to_base=gameobject)
        else:
            raise ValueError()

GameObject = GameObjectType()

def translate_from_base(gameobject, baseobject):
    """translate a key or attribute from the game object's base universe to the forked one

Implement __from_base__(self, gameobject) on the type of object being translated to override.

The default behavior of GameObjectType will create a new instance in the new universe.

Tuples will be translated recursively.

This function may be called more than once for a single object in the base universe.
The result does not have to be identical, but it must be equal and any modifications must be shared.
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
        self.games = ()

    def add_game(self, child):
        self.add_child(child)
        self.games = self.games + (child,)

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
    assert game1 in world.games
    assert game2 in world.games
    assert world.games[0].huh == 1

    world2 = world.fork()
    assert world2.games[0].huh == 1
    assert world2.games[0] != game1
    assert world2.games[0] == world2.games[0]
    world2.games[0].huh = 2
    assert world2.games[0].huh == 2
    assert game1.huh == 1

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
