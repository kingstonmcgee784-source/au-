"""MCP server for the Meteor Mayhem Roblox game.

Lets an MCP client (Claude Code, Claude Desktop, ...) read and tune the game's
settings, read its scripts, and rebuild the Roblox Studio place file.

Run with:  python3 mcp_server/server.py   (stdio transport)
"""

from __future__ import annotations

import itertools
import re
import xml.dom.minidom
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "src" / "shared" / "Config.luau"
PLACE = ROOT / "MeteorMayhem.rbxlx"

# name -> (path, Roblox class, service, container folder, instance name)
SCRIPTS = {
    "config": (CONFIG, "ModuleScript", "ReplicatedStorage", "Shared", "Config"),
    "server": (ROOT / "src/server/Main.server.luau", "Script", "ServerScriptService", "Server", "Main"),
    "client": (ROOT / "src/client/Hud.client.luau", "LocalScript", "StarterPlayerScripts", "Client", "Hud"),
}

# A top-level numeric setting line, e.g. "\tRoundLength = 60, -- comment"
SETTING = re.compile(r"^\t(\w+) = (-?\d+(?:\.\d+)?),(.*)$", re.MULTILINE)

mcp = MCPServer("meteor-mayhem")


def _settings() -> dict[str, float]:
    return {m[1]: float(m[2]) for m in SETTING.finditer(CONFIG.read_text())}


def _format(value: float) -> str:
    return str(int(value)) if value == int(value) else repr(value)


@mcp.tool()
def get_config() -> dict[str, float]:
    """Return every numeric game setting (round length, meteor timing, coin values, ...)."""
    return _settings()


@mcp.tool()
def set_config(name: str, value: float) -> str:
    """Change one numeric game setting in Config.luau.

    Use get_config to see the valid names. Run build_place afterwards so the
    place file picks up the change.
    """
    settings = _settings()
    if name not in settings:
        raise ToolError(f"Unknown setting {name!r}. Valid settings: {', '.join(sorted(settings))}")
    if value < 0:
        raise ToolError("Settings cannot be negative.")
    text = CONFIG.read_text()
    pattern = re.compile(rf"^\t{re.escape(name)} = -?\d+(?:\.\d+)?,", re.MULTILINE)
    CONFIG.write_text(pattern.sub(f"\t{name} = {_format(value)},", text, count=1))
    return f"{name}: {_format(settings[name])} -> {_format(value)}"


@mcp.tool()
def read_script(name: str) -> str:
    """Return the Luau source of a game script. `name` is "config", "server" or "client"."""
    if name not in SCRIPTS:
        raise ToolError(f"Unknown script {name!r}. Choose one of: {', '.join(SCRIPTS)}")
    return SCRIPTS[name][0].read_text()


@mcp.tool()
def build_place() -> str:
    """Rebuild MeteorMayhem.rbxlx (the file you open in Roblox Studio) from the scripts in src/."""
    refs = itertools.count(1)

    def item(cls: str, name: str, children: str = "", source: str | None = None) -> str:
        props = f'<string name="Name">{name}</string>'
        if source is not None:
            if "]]>" in source:
                raise ToolError(f"{name} contains ']]>', which cannot be stored in a place file.")
            props += f'<ProtectedString name="Source"><![CDATA[{source}]]></ProtectedString>'
        return f'<Item class="{cls}" referent="RBX{next(refs)}"><Properties>{props}</Properties>{children}</Item>'

    def script(key: str) -> str:
        path, cls, _service, folder, name = SCRIPTS[key]
        return item("Folder", folder, item(cls, name, source=path.read_text()))

    body = (
        item("Workspace", "Workspace")
        + item("ReplicatedStorage", "ReplicatedStorage", script("config"))
        + item("ServerScriptService", "ServerScriptService", script("server"))
        + item(
            "StarterPlayer",
            "StarterPlayer",
            item("StarterPlayerScripts", "StarterPlayerScripts", script("client")),
        )
    )
    document = f'<roblox version="4">{body}</roblox>\n'
    xml.dom.minidom.parseString(document)  # fail loudly rather than write a broken file
    PLACE.write_text(document)
    return f"Wrote {PLACE.name} ({len(document):,} bytes)"


if __name__ == "__main__":
    mcp.run()
