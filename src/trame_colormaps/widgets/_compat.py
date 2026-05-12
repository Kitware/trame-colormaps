"""Vuetify version compatibility helpers.

Detects whether the trame server is using Vue 2 or Vue 3 and returns
the appropriate ``trame.widgets.vuetify*`` module.

Detection is deferred to call time (not import time) so that the
application has a chance to create its server with the desired
``client_type`` first.

For Vue 2, ``trame-dataclass``'s ``provide_as`` / ``<trame-dataclass>``
component does not work (the JS bundle is Vue 3 only).  Instead we mirror
every ``ColormapConfig`` field into top-level server state under a chosen
prefix (default ``"config"``) and reference them in templates as
``config_preset``, ``config_lut_img_h``, etc.
"""


def is_v3():
    """Return True if the active trame server uses Vue 3 (Vuetify 3).

    Must be called **after** the server has been created via
    ``get_server(client_type=...)``.
    """
    try:
        from trame.app import get_server
        server = get_server()
        return server.client_type == "vue3"
    except Exception:
        return True  # default to v3


def vuetify():
    """Return the correct ``vuetify2`` or ``vuetify3`` widget module."""
    if is_v3():
        from trame.widgets import vuetify3
        return vuetify3
    else:
        from trame.widgets import vuetify2
        return vuetify2


def v2_state_prefix(config, prefix="config"):
    """Mirror a ColormapConfig's fields into server state for Vue 2.

    For every field ``foo`` on *config*, creates ``<prefix>_foo`` in the
    server state and keeps them in sync bidirectionally.

    Returns the prefix string so callers know how to build template
    variable names (e.g. ``f"{prefix}_preset"``).
    """
    server = config.server
    state = server.state
    field_names = list(config.FIELD_NAMES)

    # Push initial values
    initial = {}
    for name in field_names:
        initial[f"{prefix}_{name}"] = getattr(config, name)
    state.update(initial)

    # config → state  (when controller writes to config)
    _pushing = {"active": False}

    def _config_to_state(*_args, **_kwargs):
        if _pushing["active"]:
            return
        _pushing["active"] = True
        try:
            updates = {}
            for name in field_names:
                updates[f"{prefix}_{name}"] = getattr(config, name)
            state.update(updates)
        finally:
            _pushing["active"] = False

    # state → config  (when UI writes to state)
    state_names = [f"{prefix}_{n}" for n in field_names]

    @state.change(*state_names)
    def _state_to_config(**kwargs):
        if _pushing["active"]:
            return
        _pushing["active"] = True
        try:
            updates = {}
            for name in field_names:
                key = f"{prefix}_{name}"
                if key in kwargs:
                    updates[name] = kwargs[key]
            if updates:
                config.update(**updates)
        finally:
            _pushing["active"] = False

    # Store the flush function on the config so callers can push
    # config field values to server state after controller operations.
    if not hasattr(config, "_v2_flush_fns"):
        config._v2_flush_fns = []
    config._v2_flush_fns.append(_config_to_state)

    return prefix
