local addonName, Addon = ...

MadsTBC = MadsTBC or Addon or {}
Addon = MadsTBC
Addon.name = addonName
Addon.version = "1.0.0-alpha.1"
Addon.modules = Addon.modules or {}
Addon.listeners = Addon.listeners or {}

local accountDefaults = {
  schemaVersion = 1,
  detailLevel = "minimal",
  phaseOverride = nil,
  trackerVisible = true,
  window = {point = "CENTER", x = 0, y = 0},
}

local characterDefaults = {
  schemaVersion = 1,
  routeMode = nil,
  routeQuestIDs = {},
  routeIndex = 1,
  routePlanVersion = 0,
  deferred = {},
  recurringHistory = {},
  acknowledgedChoices = {},
  firstScanComplete = false,
}

local function applyDefaults(target, defaults)
  for key, value in pairs(defaults) do
    if target[key] == nil then
      if type(value) == "table" then
        target[key] = {}
        applyDefaults(target[key], value)
      else
        target[key] = value
      end
    elseif type(value) == "table" and type(target[key]) == "table" then
      applyDefaults(target[key], value)
    end
  end
end

function Addon:RegisterModule(name, module)
  self.modules[name] = module
  module.addon = self
end

function Addon:On(event, callback)
  self.listeners[event] = self.listeners[event] or {}
  table.insert(self.listeners[event], callback)
end

function Addon:Emit(event, ...)
  for _, callback in ipairs(self.listeners[event] or {}) do
    local ok, message = pcall(callback, ...)
    if not ok then geterrorhandler()(message) end
  end
end

function Addon:Print(message)
  DEFAULT_CHAT_FRAME:AddMessage("|cffd6a84bMad's TBC Loremaster:|r " .. tostring(message))
end

function Addon:Initialize()
  MadsTBCLoremasterDB = MadsTBCLoremasterDB or {}
  MadsTBCLoremasterCharacterDB = MadsTBCLoremasterCharacterDB or {}
  applyDefaults(MadsTBCLoremasterDB, accountDefaults)
  applyDefaults(MadsTBCLoremasterCharacterDB, characterDefaults)
  self.db = MadsTBCLoremasterDB
  self.charDB = MadsTBCLoremasterCharacterDB

  for _, name in ipairs({"Character", "Eligibility", "Router", "Navigation", "UI"}) do
    local module = self.modules[name]
    if module and module.Initialize then module:Initialize() end
  end
  if Questie and Questie.API and Questie.API.RegisterOnReady then
    Questie.API.RegisterOnReady(function() self:Rescan("questie_ready") end)
    if Questie.API.RegisterForQuestUpdates then
      Questie.API.RegisterForQuestUpdates(function() self:Rescan("questie_update") end)
    end
  end
  -- Always perform an initial character scan. RegisterOnReady is an update
  -- hook, but depending on addon load order it is not guaranteed to replay an
  -- already-fired ready notification after /reload.
  self:Rescan("login")
end

function Addon:Rescan(reason)
  if self.scanPending then return end
  self.scanPending = true
  C_Timer.After(0.15, function()
    self.scanPending = nil
    self.modules.Character:Scan()
    self.modules.Eligibility:Rebuild()
    self.modules.Router:Refresh(reason or "event")
    self:Emit("STATE_UPDATED", reason or "event")
  end)
end

function Addon:SetDetailLevel(level)
  if level ~= "minimal" and level ~= "route" and level ~= "arc" and level ~= "deep" then return end
  self.db.detailLevel = level
  self:Emit("STATE_UPDATED", "detail")
end

function Addon:SetPhaseOverride(phase)
  if phase ~= nil and (type(phase) ~= "number" or phase < 1 or phase > 5) then return end
  self.db.phaseOverride = phase
  self:Rescan("phase")
end

local frame = CreateFrame("Frame")
frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("PLAYER_LEVEL_UP")
frame:RegisterEvent("QUEST_ACCEPTED")
frame:RegisterEvent("QUEST_REMOVED")
frame:RegisterEvent("QUEST_TURNED_IN")
frame:RegisterEvent("QUEST_LOG_UPDATE")
frame:RegisterEvent("SKILL_LINES_CHANGED")
frame:RegisterEvent("UPDATE_FACTION")
frame:RegisterEvent("QUEST_DETAIL")
frame:SetScript("OnEvent", function(_, event, arg1)
  if event == "ADDON_LOADED" and arg1 == addonName then
    SLASH_MADSTBCLOREMASTER1 = "/mtl"
    SlashCmdList.MADSTBCLOREMASTER = function(message)
      message = strtrim(string.lower(message or ""))
      if message == "scan" then Addon:Rescan("manual")
      elseif message == "continue" then Addon.modules.Router:Start("continue")
      elseif message == "catchup" then Addon.modules.Router:Start("catchup")
      elseif message == "track" or message == "back" then Addon.modules.Router:Start("back_on_track")
      else Addon.modules.UI:Toggle() end
    end
  elseif event == "PLAYER_LOGIN" then
    Addon:Initialize()
  elseif event == "QUEST_DETAIL" then
    local questID = GetQuestID and GetQuestID()
    if questID and questID > 0 and Addon.modules.UI then
      Addon.modules.UI:MaybeWarnChoice(questID)
    end
  elseif event ~= "ADDON_LOADED" then
    Addon:Rescan(event)
  end
end)
