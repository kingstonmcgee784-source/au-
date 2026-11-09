-- Meteor Mayhem: heads-up display (round status + upgrade shop).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))
local status = ReplicatedStorage:WaitForChild("RoundStatus")
local buyUpgrade = ReplicatedStorage:WaitForChild("BuyUpgrade")

local player = Players.LocalPlayer
local coins = player:WaitForChild("leaderstats"):WaitForChild("Coins")

local gui = Instance.new("ScreenGui")
gui.Name = "MeteorMayhemHud"
gui.ResetOnSpawn = false

local function round(instance: GuiObject, radius: number)
	local corner = Instance.new("UICorner")
	corner.CornerRadius = UDim.new(0, radius)
	corner.Parent = instance
end

-- Round status banner
local banner = Instance.new("TextLabel")
banner.AnchorPoint = Vector2.new(0.5, 0)
banner.Position = UDim2.new(0.5, 0, 0, 12)
banner.Size = UDim2.new(0.6, 0, 0, 44)
banner.BackgroundColor3 = Color3.fromRGB(20, 22, 30)
banner.BackgroundTransparency = 0.25
banner.TextColor3 = Color3.new(1, 1, 1)
banner.Font = Enum.Font.GothamBold
banner.TextScaled = true
banner.Text = status.Value
banner.Parent = gui
round(banner, 10)

local bannerLimit = Instance.new("UITextSizeConstraint")
bannerLimit.MaxTextSize = 24
bannerLimit.Parent = banner

local bannerPadding = Instance.new("UIPadding")
bannerPadding.PaddingLeft = UDim.new(0, 12)
bannerPadding.PaddingRight = UDim.new(0, 12)
bannerPadding.Parent = banner

status.Changed:Connect(function(value)
	banner.Text = value
end)

-- Shop
local shop = Instance.new("Frame")
shop.AnchorPoint = Vector2.new(0, 1)
shop.Position = UDim2.new(0, 12, 1, -12)
shop.Size = UDim2.new(0, 220, 0, 150)
shop.BackgroundColor3 = Color3.fromRGB(20, 22, 30)
shop.BackgroundTransparency = 0.25
shop.Parent = gui
round(shop, 10)

local layout = Instance.new("UIListLayout")
layout.Padding = UDim.new(0, 6)
layout.HorizontalAlignment = Enum.HorizontalAlignment.Center
layout.VerticalAlignment = Enum.VerticalAlignment.Center
layout.SortOrder = Enum.SortOrder.LayoutOrder
layout.Parent = shop

local coinLabel = Instance.new("TextLabel")
coinLabel.LayoutOrder = 1
coinLabel.Size = UDim2.new(1, -16, 0, 30)
coinLabel.BackgroundTransparency = 1
coinLabel.TextColor3 = Color3.fromRGB(255, 210, 60)
coinLabel.Font = Enum.Font.GothamBold
coinLabel.TextSize = 20
coinLabel.Parent = shop

local buttons: { [string]: TextButton } = {}

local function makeButton(kind: string, order: number)
	local button = Instance.new("TextButton")
	button.LayoutOrder = order
	button.Size = UDim2.new(1, -16, 0, 44)
	button.TextColor3 = Color3.new(1, 1, 1)
	button.Font = Enum.Font.GothamMedium
	button.TextSize = 16
	button.AutoButtonColor = true
	button.Parent = shop
	round(button, 8)
	button.Activated:Connect(function()
		buyUpgrade:FireServer(kind)
	end)
	buttons[kind] = button
end

makeButton("Speed", 2)
makeButton("Jump", 3)

local function refresh()
	coinLabel.Text = string.format("Coins: %d", coins.Value)
	for kind, button in buttons do
		local level = player:GetAttribute(kind .. "Level") or 0
		if level >= Config.MaxUpgradeLevel then
			button.Text = string.format("%s  MAX", kind)
			button.BackgroundColor3 = Color3.fromRGB(70, 70, 80)
		else
			local cost = Config.upgradeCost(kind, level)
			button.Text = string.format("%s Lv %d  ->  %d coins", kind, level, cost)
			button.BackgroundColor3 = if coins.Value >= cost
				then Color3.fromRGB(40, 160, 90)
				else Color3.fromRGB(120, 60, 60)
		end
	end
end

coins.Changed:Connect(refresh)
player:GetAttributeChangedSignal("SpeedLevel"):Connect(refresh)
player:GetAttributeChangedSignal("JumpLevel"):Connect(refresh)
refresh()

gui.Parent = player:WaitForChild("PlayerGui")
