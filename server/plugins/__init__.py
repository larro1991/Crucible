"""
Crucible Plugin System

Plugins are Python modules in the plugins/ directory that expose:
- TOOLS: List of Tool definitions
- HANDLERS: Dict mapping tool names to async handler functions

Plugins are hot-loadable - add/remove files to enable/disable tools.
"""

import os
import sys
import json
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Callable, Optional
import logging

logger = logging.getLogger('crucible.plugins')

PLUGINS_DIR = Path(__file__).parent
CONFIG_FILE = PLUGINS_DIR / 'plugins.json'


class PluginManager:
    """Manages dynamic loading/unloading of Crucible plugins."""

    def __init__(self):
        self.plugins: Dict[str, Any] = {}  # name -> module
        self.tools: List[Any] = []  # Tool definitions
        self.handlers: Dict[str, Callable] = {}  # tool_name -> handler
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load plugin configuration."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load plugin config: {e}")
        return {"enabled": {}, "settings": {}}

    def _save_config(self):
        """Save plugin configuration."""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save plugin config: {e}")

    def discover_plugins(self) -> List[str]:
        """Find all available plugins."""
        plugins = []
        for path in PLUGINS_DIR.glob('*.py'):
            if path.name.startswith('_'):
                continue
            plugins.append(path.stem)
        return plugins

    def load_plugin(self, name: str) -> bool:
        """Load a plugin by name."""
        if name in self.plugins:
            logger.info(f"Plugin {name} already loaded")
            return True

        plugin_path = PLUGINS_DIR / f"{name}.py"
        if not plugin_path.exists():
            logger.error(f"Plugin not found: {plugin_path}")
            return False

        try:
            spec = importlib.util.spec_from_file_location(f"crucible_plugin_{name}", plugin_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"crucible_plugin_{name}"] = module
            spec.loader.exec_module(module)

            # Extract tools and handlers
            if hasattr(module, 'TOOLS'):
                for tool in module.TOOLS:
                    self.tools.append(tool)
                    logger.info(f"Registered tool: {tool.name}")

            if hasattr(module, 'HANDLERS'):
                self.handlers.update(module.HANDLERS)

            # Pass settings to plugin if it has init function
            if hasattr(module, 'init'):
                settings = self.config.get('settings', {}).get(name, {})
                module.init(settings)

            self.plugins[name] = module
            self.config['enabled'][name] = True
            self._save_config()

            logger.info(f"Loaded plugin: {name}")
            return True

        except Exception as e:
            logger.exception(f"Failed to load plugin {name}: {e}")
            return False

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin by name."""
        if name not in self.plugins:
            logger.warning(f"Plugin {name} not loaded")
            return False

        try:
            module = self.plugins[name]

            # Remove tools
            if hasattr(module, 'TOOLS'):
                tool_names = {t.name for t in module.TOOLS}
                self.tools = [t for t in self.tools if t.name not in tool_names]
                for tn in tool_names:
                    self.handlers.pop(tn, None)

            # Cleanup if plugin has cleanup function
            if hasattr(module, 'cleanup'):
                module.cleanup()

            del self.plugins[name]
            del sys.modules[f"crucible_plugin_{name}"]

            self.config['enabled'][name] = False
            self._save_config()

            logger.info(f"Unloaded plugin: {name}")
            return True

        except Exception as e:
            logger.exception(f"Failed to unload plugin {name}: {e}")
            return False

    def reload_plugin(self, name: str) -> bool:
        """Reload a plugin (unload + load)."""
        self.unload_plugin(name)
        return self.load_plugin(name)

    def load_enabled_plugins(self):
        """Load all plugins marked as enabled in config."""
        for name, enabled in self.config.get('enabled', {}).items():
            if enabled:
                self.load_plugin(name)

    def get_tools(self) -> List[Any]:
        """Get all registered tools from plugins."""
        return self.tools

    async def handle_tool(self, name: str, args: Dict[str, Any]) -> Optional[str]:
        """Handle a tool call if it's from a plugin."""
        if name in self.handlers:
            handler = self.handlers[name]
            return await handler(args)
        return None

    def status(self) -> str:
        """Get plugin system status."""
        available = self.discover_plugins()
        loaded = list(self.plugins.keys())

        lines = [
            "=== Crucible Plugin System ===",
            f"Available plugins: {', '.join(available) or 'none'}",
            f"Loaded plugins: {', '.join(loaded) or 'none'}",
            f"Registered tools: {len(self.tools)}",
            ""
        ]

        for name in loaded:
            module = self.plugins[name]
            tool_count = len(module.TOOLS) if hasattr(module, 'TOOLS') else 0
            lines.append(f"  {name}: {tool_count} tools")

        return '\n'.join(lines)


# Singleton instance
_manager: Optional[PluginManager] = None

def get_plugin_manager() -> PluginManager:
    """Get the plugin manager singleton."""
    global _manager
    if _manager is None:
        _manager = PluginManager()
    return _manager
