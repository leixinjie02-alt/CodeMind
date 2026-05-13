
class Parent:
    pass

class Child(Parent):
    """This is a child class."""
    def method_a(self, x):
        print(x)
        self.helper()

    def helper(self):
        return 1

def top_level_func():
    c = Child()
    c.method_a(10)
