"""ComfyUI Discord Rich Presence Extension.

Hooks into ComfyUI's execution pipeline to display generation
status in Discord via Rich Presence.
"""

import logging

logger = logging.getLogger("discord_rpc")

# Required by ComfyUI - can be empty since this is a service extension, not a node provider
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]


def _ensure_pypresence():
    """Make sure the ``pypresence`` dependency is importable.

    ComfyUI does not auto-install custom-node requirements on its own (only
    ComfyUI-Manager does, at install time).  So users who install this
    extension manually - or who rebuild their virtual environment - end up
    without ``pypresence``.  To keep the extension working in every install
    scenario we install it automatically into the *current* interpreter the
    first time it is missing.

    Returns True if pypresence is importable after this call, else False.
    """
    try:
        import pypresence  # noqa: F401
        return True
    except ImportError:
        pass

    import subprocess
    import sys

    logger.info(
        "[Discord RPC] pypresence not found - installing automatically..."
    )
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pypresence>=4.3.0"]
        )
    except Exception as e:
        logger.error(
            "[Discord RPC] Automatic install of pypresence failed (%s). "
            "Please install it manually with: pip install pypresence",
            e,
        )
        return False

    # Refresh import caches so the freshly installed package is visible
    import importlib

    importlib.invalidate_caches()
    try:
        import pypresence  # noqa: F401

        logger.info("[Discord RPC] pypresence installed successfully.")
        return True
    except ImportError:
        logger.error(
            "[Discord RPC] pypresence was installed but could not be "
            "imported. Please restart ComfyUI."
        )
        return False


def _init_discord_rpc():
    """Initialize the Discord RPC system."""
    if not _ensure_pypresence():
        return

    from .config import load_config, get_config, set_rpc_manager, register_routes
    from .discord_rpc_manager import DiscordRPCManager
    from .state_tracker import StateTracker

    config = load_config()
    if not config.get("enabled", True):
        logger.info("[Discord RPC] Disabled by configuration")
        # Still register routes so settings UI can re-enable it
        try:
            from server import PromptServer

            if hasattr(PromptServer, "instance") and PromptServer.instance is not None:
                register_routes(PromptServer.instance.app)
        except Exception:
            pass
        return

    client_id = config.get("client_id", "1470194985893888167")

    # Get ComfyUI user directory for lockfile
    user_dir = ""
    try:
        import folder_paths
        user_dir = folder_paths.get_user_directory()
    except Exception:
        pass

    # Create the RPC manager
    rpc_manager = DiscordRPCManager(client_id, config, user_dir=user_dir)
    set_rpc_manager(rpc_manager)

    # Create the state tracker
    state_tracker = StateTracker(rpc_manager)

    # --- Hook into ComfyUI ---
    try:
        from server import PromptServer

        if hasattr(PromptServer, "instance") and PromptServer.instance is not None:
            server = PromptServer.instance

            # Hook 1: on_prompt_handler for workflow metadata extraction
            server.add_on_prompt_handler(state_tracker.on_prompt)

            # Hook 2: Wrap send_sync to catch execution lifecycle events
            original_send_sync = server.send_sync

            def wrapped_send_sync(event, data, sid=None):
                try:
                    if get_config().get("debug_logging", False):
                        if event in ("execution_start", "progress", "executing",
                                     "execution_error", "execution_interrupted"):
                            logger.info(f"[Discord RPC] Event: {event}")
                    state_tracker.on_server_event(event, data)
                except Exception as e:
                    logger.warning(f"[Discord RPC] Event handler error ({event}): {e}")
                return original_send_sync(event, data, sid)

            server.send_sync = wrapped_send_sync

            # Hook 3: Register API routes
            register_routes(server.app)

            logger.info("[Discord RPC] Server hooks registered")
    except Exception as e:
        logger.warning(f"[Discord RPC] Failed to register server hooks: {e}")

    # Note: Progress is captured via the send_sync("progress", ...) event
    # in the wrapped send_sync above.  We do NOT monkey-patch
    # add_progress_handler() because execution.py imports it by name
    # at module load time (`from ... import add_progress_handler`),
    # so a module-level patch is invisible to the executor.

    # Start the RPC manager (connects to Discord in background thread)
    rpc_manager.start()
    logger.info("[Discord RPC] Extension initialized successfully")


# Initialize when the module is loaded by ComfyUI
try:
    _init_discord_rpc()
except Exception as e:
    logger.error(f"[Discord RPC] Failed to initialize: {e}")
