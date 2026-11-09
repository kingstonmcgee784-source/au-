# Meteor Mayhem

An original round-based Roblox survival game. Meteors rain down on a floating
arena and blow holes in the floor. Dodge them, grab coins, outlast the timer,
and spend your coins on permanent Speed and Jump upgrades.

## How it plays

1. Players wait in the lobby during a 15 second intermission.
2. Everyone is teleported to the arena for a 60 second round.
3. A red marker grows on the floor wherever a meteor is about to land. Standing
   in it at impact knocks you out, and the tiles under it are destroyed.
4. Meteors fall faster as the round goes on. Fall through a hole and you're out.
5. Coins appear on the arena (+5 each). Survivors earn a +25 bonus and a Win.
6. Spend coins in the shop (bottom left) on Speed and Jump, up to level 10.

Coins, wins and upgrades are saved with a DataStore.

## Getting it into Roblox Studio

The whole world is built by script, so there are no models to import.

### Option A: Rojo (recommended)

Install [Rojo](https://rojo.space), then from this folder:

```bash
rojo build -o MeteorMayhem.rbxlx
```

Open `MeteorMayhem.rbxlx` in Roblox Studio and press Play. Or run `rojo serve`
and connect with the Rojo Studio plugin to live-sync edits.

### Option B: Copy and paste

In a new Baseplate place in Studio (you can delete the Baseplate and its SpawnLocation):

| Create this                                                        | Paste the contents of        |
| ------------------------------------------------------------------ | ---------------------------- |
| `ReplicatedStorage` > Folder `Shared` > **ModuleScript** `Config`  | `src/shared/Config.luau`     |
| `ServerScriptService` > **Script** `Main`                          | `src/server/Main.server.luau`|
| `StarterPlayer` > `StarterPlayerScripts` > **LocalScript** `Hud`   | `src/client/Hud.client.luau` |

The names `Shared` and `Config` must match exactly.

### Saving progress

Saving only works in a published place. To test it in Studio, publish the game
and turn on **Game Settings > Security > Enable Studio Access to API Services**.
Without that the game still runs; it just doesn't save.

## Tweaking

Everything adjustable (round length, meteor speed, arena size, coin values,
upgrade costs) lives in `src/shared/Config.luau`.
