import traceback


def rerun_after_exception(error, retries):
    def decorator(func):
        def wrapper(*args, **kwargs):
            n = 0
            while n <= retries:
                try:
                    ret = func(*args, **kwargs)
                except error:
                    print(f'Caught {error}, rerunning {func.__name__}!')
                    n += 1
                else:
                    return ret
        return wrapper
    return decorator


def send_exceptions_to_slack(remote):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                ret = func(*args, **kwargs)
            except Error as e:
                if remote:
                    send_warning(traceback.format_exc())
                raise
            else:
                return ret
        return wrapper
    return decorator

