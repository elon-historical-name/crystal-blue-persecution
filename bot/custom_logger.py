import functools
import logging
import os
import sys
import types


def update_module_class(mod):
    class CachingModule(types.ModuleType):
        pass
    mod.__class__ = CachingModule


def mod_property(func, cached=False):
    func_name = func.__name__
    if '.' in func_name:
        raise ValueError('mod_property only applicable to top-level module functions')
    func_mod = sys.modules[func.__module__]
    if func_mod.__class__ == types.ModuleType:
        update_module_class(func_mod)
    elif func_mod.__class__.__name__ != 'CachingModule':
        raise RuntimeError(f'mod_property incompatible with module type: {func_mod.__name__}({func_mod.__class__.__qualname__})')

    @functools.wraps(func)
    def wrapper(mod):
        value = func()
        if cached:
            setattr(func_mod.__class__, func_name, value)
            delattr(func_mod, func_name)
        return value
    wrapper.__name__ = func_name
    setattr(func_mod.__class__, func_name, property(wrapper))
    return wrapper


def cached_mod_property(func):
    return mod_property(func, cached=True)


@cached_mod_property
def logger() -> logging.Logger:
    log_format = '%(asctime)s %(levelname)-8s %(message)s' \
        if os.environ.get("IS_DOCKERIZED") != "1" \
        else '%(levelname)-8s %(message)s'
    formatter = logging.Formatter(
        fmt=log_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    screen_handler = logging.StreamHandler(stream=sys.stdout)
    screen_handler.setFormatter(formatter)
    new_logger = logging.getLogger("bot")
    new_logger.setLevel(logging.INFO)
    new_logger.addHandler(screen_handler)
    return new_logger
