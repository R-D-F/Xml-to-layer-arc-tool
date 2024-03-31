import os
import sys
from copy import copy
from importlib import reload
from glob import glob

def reload_modules(root):
    folders = [os.path.basename(d) for d in glob(f'{root}/*')
               if os.path.isdir(d)]
    sys_modules = copy(sys.modules)
    for module in sys_modules:
        for folder in folders:
            if str(module).startswith(folder):
                try:
                    reload(sys_modules[module])
                except (ModuleNotFoundError, AttributeError):
                    pass