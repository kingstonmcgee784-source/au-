-- Meteor Mayhem: server game logic.
-- Builds the world, runs rounds, spawns meteors and coins, and saves progress.

local DataStoreService = game:GetService("DataStoreService")
local Debris = game:GetService("Debris")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))

local rng = Random.new()

----------------------------------------------------------------------
-- Replicated state and remotes
----------------------------------------------------------------------

local status = Instance.new("StringValue")
status.Name = "RoundStatus"
status.Value = "Loading..."
status.Parent = ReplicatedStorage

local buyUpgrade = Instance.new("RemoteEvent")
buyUpgrade.Name = "BuyUpgrade"
buyUpgrade.Parent = ReplicatedStorage

----------------------------------------------------------------------
-- World
----------------------------------------------------------------------

local function makePart(props: { [string]: any }): Part
	local part = Instance.new("Part")
	part.Anchored = true
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	local parent = props.Parent
	for key, value in props do
		if key ~= "Parent" then
			(part :: any)[key] = value
		end
	end
	part.Parent = parent
	return part
end

local world = Instance.new("Folder")
world.Name = "MeteorMayhem"
world.Parent = workspace

local arenaFolder = Instance.new("Folder")
arenaFolder.Name = "Arena"
arenaFolder.Parent = world

local coinFolder = Instance.new("Folder")
coinFolder.Name = "Coins"
coinFolder.Parent = world

local effectsFolder = Instance.new("Folder")
effectsFolder.Name = "Effects"
effectsFolder.Parent = world

-- Lobby
makePart({
	Name = "LobbyFloor",
	Size = Vector3.new(70, 2, 70),
	Position = Config.LobbyCenter,
	Color = Color3.fromRGB(60, 70, 95),
	Material = Enum.Material.SmoothPlastic,
	Parent = world,
})

for _, offset in { Vector3.new(35, 0, 0), Vector3.new(-35, 0, 0), Vector3.new(0, 0, 35), Vector3.new(0, 0, -35) } do
	makePart({
		Name = "LobbyWall",
		Size = if offset.X ~= 0 then Vector3.new(2, 8, 72) else Vector3.new(72, 8, 2),
		Position = Config.LobbyCenter + offset + Vector3.new(0, 5, 0),
		Color = Color3.fromRGB(90, 200, 255),
		Material = Enum.Material.Neon,
		Transparency = 0.6,
		Parent = world,
	})
end

local spawnLocation = Instance.new("SpawnLocation")
spawnLocation.Anchored = true
spawnLocation.Size = Vector3.new(12, 1, 12)
spawnLocation.Position = Config.LobbyCenter + Vector3.new(0, 1.5, 0)
spawnLocation.Color = Color3.fromRGB(90, 200, 255)
spawnLocation.Material = Enum.Material.Neon
spawnLocation.TopSurface = Enum.SurfaceType.Smooth
spawnLocation.Neutral = true
spawnLocation.Parent = world

-- Anything that falls off the map touches this and is knocked out.
local killFloor = makePart({
	Name = "KillFloor",
	Size = Vector3.new(2048, 4, 2048),
	Position = Vector3.new(0, Config.ArenaCenter.Y - 70, 0),
	Transparency = 1,
	CanCollide = false,
	Parent = world,
})
killFloor.Touched:Connect(function(hit)
	local humanoid = hit.Parent and hit.Parent:FindFirstChildOfClass("Humanoid")
	if humanoid and humanoid.Health > 0 then
		humanoid.Health = 0
	end
end)

-- Arena tiles
local tiles: { Part } = {}
do
	local half = (Config.GridSize - 1) / 2
	for x = 0, Config.GridSize - 1 do
		for z = 0, Config.GridSize - 1 do
			local dark = (x + z) % 2 == 0
			local tile = makePart({
				Name = "Tile",
				Size = Vector3.new(Config.TileSize, 2, Config.TileSize),
				Position = Config.ArenaCenter
					+ Vector3.new((x - half) * Config.TileSize, 0, (z - half) * Config.TileSize),
				Color = if dark then Color3.fromRGB(70, 75, 90) else Color3.fromRGB(95, 100, 120),
				Material = Enum.Material.Slate,
				Parent = arenaFolder,
			})
			tile:SetAttribute("Intact", true)
			table.insert(tiles, tile)
		end
	end
end

local function setTileIntact(tile: Part, intact: boolean)
	tile:SetAttribute("Intact", intact)
	tile.CanCollide = intact
	tile.Transparency = if intact then 0 else 1
end

local function restoreArena()
	for _, tile in tiles do
		setTileIntact(tile, true)
	end
	coinFolder:ClearAllChildren()
	effectsFolder:ClearAllChildren()
end

local function randomIntactTile(): Part?
	local intact = {}
	for _, tile in tiles do
		if tile:GetAttribute("Intact") then
			table.insert(intact, tile)
		end
	end
	if #intact == 0 then
		return nil
	end
	return intact[rng:NextInteger(1, #intact)]
end

----------------------------------------------------------------------
-- Player data
----------------------------------------------------------------------

type PlayerData = {
	loaded: boolean, -- only save data that was successfully loaded
	coins: IntValue,
	wins: IntValue,
}

local store: DataStore? = nil
do
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore("MeteorMayhem_v1")
	end)
	if ok then
		store = result
	else
		warn("[MeteorMayhem] DataStore unavailable, progress will not save:", result)
	end
end

local playerData: { [Player]: PlayerData } = {}
local alive: { [Player]: boolean } = {}

local function applyUpgrades(player: Player)
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	if not humanoid then
		return
	end
	local speed = Config.Upgrades.Speed
	local jump = Config.Upgrades.Jump
	humanoid.WalkSpeed = speed.Base + speed.PerLevel * (player:GetAttribute("SpeedLevel") or 0)
	humanoid.UseJumpPower = true
	humanoid.JumpPower = jump.Base + jump.PerLevel * (player:GetAttribute("JumpLevel") or 0)
end

local function onCharacterAdded(player: Player, character: Model)
	local humanoid = character:WaitForChild("Humanoid", 10)
	if not humanoid or not humanoid:IsA("Humanoid") then
		return
	end
	applyUpgrades(player)
	humanoid.Died:Connect(function()
		alive[player] = nil
	end)
end

local function savePlayer(player: Player)
	local data = playerData[player]
	if not (store and data and data.loaded) then
		return
	end
	local ok, err = pcall(function()
		store:SetAsync(tostring(player.UserId), {
			coins = data.coins.Value,
			wins = data.wins.Value,
			speed = player:GetAttribute("SpeedLevel") or 0,
			jump = player:GetAttribute("JumpLevel") or 0,
		})
	end)
	if not ok then
		warn("[MeteorMayhem] Failed to save", player.Name, err)
	end
end

local function onPlayerAdded(player: Player)
	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"

	local coins = Instance.new("IntValue")
	coins.Name = "Coins"
	coins.Parent = leaderstats

	local wins = Instance.new("IntValue")
	wins.Name = "Wins"
	wins.Parent = leaderstats

	player:SetAttribute("SpeedLevel", 0)
	player:SetAttribute("JumpLevel", 0)
	leaderstats.Parent = player

	local data: PlayerData = { loaded = false, coins = coins, wins = wins }
	playerData[player] = data

	player.CharacterAdded:Connect(function(character)
		onCharacterAdded(player, character)
	end)
	if player.Character then
		task.spawn(onCharacterAdded, player, player.Character)
	end

	if store then
		local ok, saved = pcall(function()
			return store:GetAsync(tostring(player.UserId))
		end)
		if not player.Parent then
			return
		end
		if ok then
			if typeof(saved) == "table" then
				-- Add to (rather than overwrite) anything earned while loading.
				coins.Value += tonumber(saved.coins) or 0
				wins.Value += tonumber(saved.wins) or 0
				local max = Config.MaxUpgradeLevel
				player:SetAttribute("SpeedLevel", math.clamp(tonumber(saved.speed) or 0, 0, max))
				player:SetAttribute("JumpLevel", math.clamp(tonumber(saved.jump) or 0, 0, max))
				applyUpgrades(player)
			end
			data.loaded = true
		else
			warn("[MeteorMayhem] Failed to load", player.Name, saved)
		end
	end
end

Players.PlayerAdded:Connect(onPlayerAdded)
for _, player in Players:GetPlayers() do
	task.spawn(onPlayerAdded, player)
end

Players.PlayerRemoving:Connect(function(player)
	alive[player] = nil
	savePlayer(player)
	playerData[player] = nil
end)

game:BindToClose(function()
	for _, player in Players:GetPlayers() do
		task.spawn(savePlayer, player)
	end
	task.wait(2)
end)

----------------------------------------------------------------------
-- Shop
----------------------------------------------------------------------

buyUpgrade.OnServerEvent:Connect(function(player, kind)
	if kind ~= "Speed" and kind ~= "Jump" then
		return
	end
	local data = playerData[player]
	if not data then
		return
	end
	local attribute = kind .. "Level"
	local level = player:GetAttribute(attribute) or 0
	if level >= Config.MaxUpgradeLevel then
		return
	end
	local cost = Config.upgradeCost(kind, level)
	if data.coins.Value < cost then
		return
	end
	data.coins.Value -= cost
	player:SetAttribute(attribute, level + 1)
	applyUpgrades(player)
end)

----------------------------------------------------------------------
-- Coins
----------------------------------------------------------------------

local function spawnCoin()
	if #coinFolder:GetChildren() >= Config.MaxCoinsOnArena then
		return
	end
	local tile = randomIntactTile()
	if not tile then
		return
	end
	local coin = makePart({
		Name = "Coin",
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(0.5, 3, 3),
		CFrame = CFrame.new(tile.Position + Vector3.new(0, 3.5, 0)) * CFrame.Angles(0, rng:NextNumber(0, math.pi), 0),
		Color = Color3.fromRGB(255, 210, 60),
		Material = Enum.Material.Neon,
		CanCollide = false,
	})
	local taken = false
	coin.Touched:Connect(function(hit)
		if taken then
			return
		end
		local player = Players:GetPlayerFromCharacter(hit.Parent)
		local data = player and playerData[player]
		if player and data and alive[player] then
			taken = true
			data.coins.Value += Config.CoinValue
			coin:Destroy()
		end
	end)
	coin.Parent = coinFolder
end

----------------------------------------------------------------------
-- Meteors
----------------------------------------------------------------------

local function meteorImpact(position: Vector3)
	local explosion = Instance.new("Explosion")
	explosion.Position = position
	explosion.BlastRadius = Config.BlastRadius
	explosion.BlastPressure = 0
	explosion.DestroyJointRadiusPercent = 0 -- visual only; damage is handled below
	explosion.Parent = effectsFolder
	Debris:AddItem(explosion, 3)

	for _, tile in tiles do
		if tile:GetAttribute("Intact") then
			local offset = tile.Position - position
			if Vector3.new(offset.X, 0, offset.Z).Magnitude <= Config.CraterRadius then
				setTileIntact(tile, false)
			end
		end
	end

	-- Collect first: setting Health fires Died, which edits `alive`.
	local victims = {}
	for player in alive do
		local character = player.Character
		local root = character and character:FindFirstChild("HumanoidRootPart")
		local humanoid = character and character:FindFirstChildOfClass("Humanoid")
		if root and humanoid and (root.Position - position).Magnitude <= Config.BlastRadius then
			table.insert(victims, humanoid)
		end
	end
	for _, humanoid in victims do
		humanoid.Health = 0
	end
end

local function pickMeteorTarget(): Vector3?
	if rng:NextNumber() < Config.TargetPlayerChance then
		local targets = {}
		for player in alive do
			local root = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
			if root then
				table.insert(targets, root.Position)
			end
		end
		if #targets > 0 then
			local position = targets[rng:NextInteger(1, #targets)]
			return Vector3.new(position.X, Config.ArenaCenter.Y + 1, position.Z)
		end
	end
	local tile = randomIntactTile()
	return if tile then tile.Position + Vector3.new(0, 1, 0) else nil
end

local function launchMeteor(roundId: number, isCurrentRound: (number) -> boolean)
	local target = pickMeteorTarget()
	if not target then
		return
	end
	local warnTime = Config.MeteorWarnTime

	-- Growing red marker on the ground shows where the meteor will land.
	local marker = makePart({
		Name = "Warning",
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(0.2, 2, 2),
		CFrame = CFrame.new(target + Vector3.new(0, 0.15, 0)) * CFrame.Angles(0, 0, math.pi / 2),
		Color = Color3.fromRGB(255, 40, 40),
		Material = Enum.Material.Neon,
		Transparency = 0.35,
		CanCollide = false,
		Parent = effectsFolder,
	})
	local diameter = Config.BlastRadius * 2
	TweenService:Create(marker, TweenInfo.new(warnTime, Enum.EasingStyle.Linear), {
		Size = Vector3.new(0.2, diameter, diameter),
	}):Play()

	local meteor = makePart({
		Name = "Meteor",
		Shape = Enum.PartType.Ball,
		Size = Vector3.new(7, 7, 7),
		Position = target + Vector3.new(rng:NextNumber(-40, 40), 160, rng:NextNumber(-40, 40)),
		Color = Color3.fromRGB(255, 120, 30),
		Material = Enum.Material.Neon,
		CanCollide = false,
		Parent = effectsFolder,
	})
	local fire = Instance.new("Fire")
	fire.Size = 14
	fire.Heat = 0
	fire.Parent = meteor
	TweenService:Create(meteor, TweenInfo.new(warnTime, Enum.EasingStyle.Quad, Enum.EasingDirection.In), {
		Position = target,
	}):Play()

	task.delay(warnTime, function()
		marker:Destroy()
		meteor:Destroy()
		if isCurrentRound(roundId) then
			meteorImpact(target)
		end
	end)
end

----------------------------------------------------------------------
-- Round loop
----------------------------------------------------------------------

local currentRound = 0
local roundActive = false

local function isCurrentRound(roundId: number): boolean
	return roundActive and roundId == currentRound
end

local function countAlive(): number
	local count = 0
	for _ in alive do
		count += 1
	end
	return count
end

local function teleport(player: Player, position: Vector3)
	local character = player.Character
	if character then
		character:PivotTo(CFrame.new(position))
	end
end

local function runRound()
	currentRound += 1
	local roundId = currentRound

	-- Send every living player to the arena.
	table.clear(alive)
	for _, player in Players:GetPlayers() do
		local character = player.Character
		local humanoid = character and character:FindFirstChildOfClass("Humanoid")
		local tile = randomIntactTile()
		if humanoid and humanoid.Health > 0 and tile then
			alive[player] = true
			teleport(player, tile.Position + Vector3.new(0, 5, 0))
		end
	end
	if countAlive() == 0 then
		return
	end

	roundActive = true
	local elapsed = 0
	local nextMeteor = 2 -- short grace period before the first meteor
	local nextCoin = 0

	while elapsed < Config.RoundLength and countAlive() > 0 do
		local dt = task.wait(0.1)
		elapsed += dt

		if elapsed >= nextMeteor then
			launchMeteor(roundId, isCurrentRound)
			local progress = math.clamp(elapsed / Config.RoundLength, 0, 1)
			nextMeteor = elapsed
				+ Config.MeteorIntervalStart
				+ (Config.MeteorIntervalEnd - Config.MeteorIntervalStart) * progress
		end

		if elapsed >= nextCoin then
			spawnCoin()
			nextCoin = elapsed + Config.CoinInterval
		end

		status.Value = string.format(
			"Survive! %ds left  |  %d alive",
			math.max(0, math.ceil(Config.RoundLength - elapsed)),
			countAlive()
		)
	end
	roundActive = false

	-- Reward survivors and bring them home.
	local survivors = {}
	for player in alive do
		table.insert(survivors, player.Name)
		local data = playerData[player]
		if data then
			data.coins.Value += Config.SurviveBonus
			data.wins.Value += 1
		end
		teleport(player, Config.LobbyCenter + Vector3.new(rng:NextNumber(-10, 10), 6, rng:NextNumber(-10, 10)))
	end
	table.clear(alive)

	if #survivors == 0 then
		status.Value = "Everyone was flattened! No survivors."
	elseif #survivors <= 3 then
		status.Value = string.format("Survived: %s  (+%d coins)", table.concat(survivors, ", "), Config.SurviveBonus)
	else
		status.Value = string.format("%d players survived!  (+%d coins)", #survivors, Config.SurviveBonus)
	end
	task.wait(Config.EndScreenTime)
end

while true do
	restoreArena()
	for remaining = Config.Intermission, 1, -1 do
		if #Players:GetPlayers() == 0 then
			status.Value = "Waiting for players..."
		else
			status.Value = string.format("Next round in %d  |  Spend coins in the shop!", remaining)
		end
		task.wait(1)
	end
	runRound()
end
