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

class Condition:
    pass

class GameObjectType(type):
    pass

class GameObject(metaclass=GameObjectType):
    parent = None

    def __init__(self, parent=None):
        self.children = []
        if parent is not None:
            self.parent = parent
        # TODO: add class children

    def add_child(self, child):
        if child.parent is not None:
            child.parent.remove_child(child) #TODO
        child.parent = self
        child._root = None
        self.children.append(child)

class Choice(GameObject):
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
    pass

# TODO: Move this
if __name__ == '__main__':
    world = World()
    maze = MazeGame()
    world.add_game(maze)

