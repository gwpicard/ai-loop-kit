def add(items, name):
    return items if name in items else [*items, name]
