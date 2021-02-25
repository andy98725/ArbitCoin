def getFile(prompt, default):
    f = input(prompt)
    if f:
        return f
    else:
        return default
