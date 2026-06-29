"""Module with issues that cannot be automatically fixed."""

import this_module_does_not_exist
from another_missing import something

class BrokenBase:
    def method(self):
        return undefined_variable

def orphan_function():
    for i in range(undefined):
        yield missing_thing
