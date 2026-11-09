-- Tunable settings shared by the server and the client.
local Config = {
	-- Round flow (seconds)
	Intermission = 15,
	RoundLength = 60,
	EndScreenTime = 5,

	-- Arena
	GridSize = 12, -- tiles per side
	TileSize = 8, -- studs
	ArenaCenter = Vector3.new(0, 50, 0),
	LobbyCenter = Vector3.new(0, 50, 220),

	-- Meteors
	MeteorWarnTime = 1.4, -- seconds between the warning marker and impact
	MeteorIntervalStart = 1.0, -- seconds between meteors at round start
	MeteorIntervalEnd = 0.22, -- seconds between meteors at round end
	BlastRadius = 9, -- players this close to an impact are knocked out
	CraterRadius = 7, -- tiles this close to an impact are destroyed
	TargetPlayerChance = 0.45, -- chance a meteor aims at a player

	-- Coins
	CoinInterval = 1.5,
	CoinValue = 5,
	MaxCoinsOnArena = 25,
	SurviveBonus = 25,

	-- Upgrades
	MaxUpgradeLevel = 10,
	Upgrades = {
		Speed = { BaseCost = 30, Base = 16, PerLevel = 2 },
		Jump = { BaseCost = 30, Base = 50, PerLevel = 5 },
	},
}

-- Cost of going from `level` to `level + 1`.
function Config.upgradeCost(kind: string, level: number): number
	return Config.Upgrades[kind].BaseCost * (level + 1)
end

return Config
