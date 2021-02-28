import threading


def getFile(prompt, default):
    f = input(prompt)
    if f:
        return f
    else:
        return default


def synchronized(method):
    
    outer_lock = threading.Lock()
#     lock_name = "__"+method.__name__+"_lock"+"__"
    lock_name = "__lock__"
    
    def sync_method(self, *args, **kws):
        with outer_lock:
            if not hasattr(self, lock_name):
                setattr(self, lock_name, threading.Lock())
            lock = getattr(self, lock_name)
        
        with lock:
            return method(self, *args, **kws)  

    return sync_method
