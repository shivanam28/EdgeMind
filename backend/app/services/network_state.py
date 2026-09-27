# In-memory app state — simple and sufficient for a hackathon demo.
# Resets to True (online) every time the server restarts.
_is_online = True

def set_online(status: bool):
    global _is_online
    _is_online = status

def is_online() -> bool:
    return _is_online