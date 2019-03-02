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
#  all GameObject's have a fork_base, the last object in their history created by forking
#  all GameObject's have a fork_object, which is fork_base if it was created by forking, another object if created by accessing a GameObject attribute
#  GameObject does not have a __dict__ but has a world_dictinary
#  world_dictionary keys are (object, name)
#  world_dictionary values must be immutable or a GameObject
#  accessing a GameObject attribute of a GameObject creates a new GameObject with fork_object of that object (unless it is already fork_object)
#    the object may have a base_world_dictionary, base_fork_base, base_fork_object if we decide not to copy the world dictionary when forking
#    an object's base_world_dictionary had best be frozen
#    if there is a world dictionary, we must either copy it or the base world dictionary when forking
#    when copying a dictionary, we must translate base_fork_object to the new fork_object
#  functions are converted to "game object methods" which have knowledge of the method they replace
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
                    for (obj, key), value in base.base_world_dictionary.items():
                        if obj == base.base_fork_object:
                            obj = self.base_fork_object
                        base_dict[obj, key] = value
                base_dict.update(base.world_dictionary)
                self.base_world_dictionary = FrozenDict(base_dict)
            else:
                self.base_world_dictionary = base.base_world_dictionary
                self.base_fork_base = base.base_fork_base
                self.base_fork_object = base.base_fork_object
                for (obj, key), value in base.world_dictionary.items():
                    if obj == base:
                        obj = self
                    self.world_dictionary[obj, key] = value
            return

        # no special forms, fall back to generic
        self.base_world_dictionary = None
        self.base_fork_base = None
        self.base_fork_object = None
        self.world_dictionary = {}
        self.fork_base = self
        self.fork_object = self
        self.__special_init__(*args, **kwargs)

    def __setattr__(self, name, value):
        if name in _gameobject_slots:
            object.__setattr__(self, name, value)
            return
        self.world_dictionary[self.fork_object, name] = value

    def __getattribute__(self, name):
        if name not in _gameobject_slots:
            try:
                return self.world_dictionary[self.fork_object, name]
            except KeyError:
                if self.base_world_dictionary:
                    try:
                        return self.base_world_dictionary[self.base_fork_object, name]
                    except KeyError:
                        pass
        return object.__getattribute__(self, name)

    def fork(self):
        """create a copy of this game object and all related objects"""
        return type(self)(forked_from=self)

    def __special_init__(self, *args, **kwargs):
        """subclass to handle arguments to this type or instances of it"""
        if args:
            raise TypeError("GameObjectType takes no positional arguments")
        for key in kwargs:
            setattr(self, key, kwargs[key])

    def __call__(self, *args, **kwargs):
        result = self.fork()
        result.__special_init__(*args, **kwargs)
        return result

GameObject = GameObjectType()

class ChoiceType(GameObjectType):
    default = None

Choice = ChoiceType()

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

"""first attempt
class Choice(GameObject):
    default = None

    def __init__(self, default=None):
        self.default = default

class NumericalChoice(Choice):
    minimum = None
    maximum = None

    def __init__(self, default=None, min=None, Max=None):
        Choice.__init__(self, default)
        self.minimum = min
        self.maximum = max

class IntegerChoice(NumericalChoice):
    pass

class World(GameObject):
    def __init__(self, parent=None):
        GameObject.__init__(self, parent)
        self.games = []

    def add_game(self, child):
        self.add_child(child)
        self.games.append(child)

class Game(GameObject):
    pass

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
