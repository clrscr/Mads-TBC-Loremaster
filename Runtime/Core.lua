local addonName, namespace = ...
MadsTBC = MadsTBC or namespace or {}
local Addon = MadsTBC
Addon.name, Addon.version = addonName, "1.0.0-alpha.5"
Addon.modules, Addon.listeners = {}, {}
Addon.status = "Waiting for login and Questie…"

function Addon:Copy(value)
  if type(value) ~= "table" then return value end
  local result = {}
  for k, v in pairs(value) do result[k] = self:Copy(v) end
  return result
end
function Addon:IsNumber(value)
  return type(value) == "number" and value == value and value > -math.huge and value < math.huge
end
function Addon:IsID(value)
  return self:IsNumber(value) and value > 0 and value == math.floor(value)
end
function Addon:Import(name)
  if not QuestieLoader then return nil end
  local ok, module = pcall(QuestieLoader.ImportModule, QuestieLoader, name)
  if ok and type(module) == "table" then return module end
end
function Addon:RegisterModule(name, module)
  self.modules[name], module.addon = module, self
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
  if DEFAULT_CHAT_FRAME then DEFAULT_CHAT_FRAME:AddMessage("|cffd6a84bMad's TBC Loremaster:|r " .. tostring(message)) end
end

local points = {CENTER=true, TOP=true, BOTTOM=true, LEFT=true, RIGHT=true, TOPLEFT=true, TOPRIGHT=true, BOTTOMLEFT=true, BOTTOMRIGHT=true}
local function position(value, default)
  value = type(value) == "table" and value or {}
  return {point=points[value.point] and value.point or default.point,
    x=Addon:IsNumber(value.x) and math.max(-10000, math.min(10000, value.x)) or default.x,
    y=Addon:IsNumber(value.y) and math.max(-10000, math.min(10000, value.y)) or default.y}
end
local function flags(value)
  local result = {}
  for id, enabled in pairs(type(value) == "table" and value or {}) do
    if Addon:IsID(id) and enabled == true then result[id] = true end
  end
  return result
end
local modes = {journey=true, continue=true, catchup=true, back_on_track=true, zone=true, cleanup=true, recurring=true, quest=true}
function Addon:NormalizeSavedVariables()
  local db = type(MadsTBCLoremasterDB) == "table" and MadsTBCLoremasterDB or {}
  local char = type(MadsTBCLoremasterCharacterDB) == "table" and MadsTBCLoremasterCharacterDB or {}
  db.window = position(db.window, {point="CENTER", x=0, y=0})
  db.tracker = position(db.tracker, {point="RIGHT", x=-45, y=40})
  db.trackerVisible = db.trackerVisible ~= false
  local minimap = type(db.minimap) == "table" and db.minimap or {}
  db.minimap = {minimapPos=self:IsNumber(minimap.minimapPos) and minimap.minimapPos%360 or 135, hide=false}
  if not ({minimal=true, route=true, arc=true, deep=true})[db.detailLevel] then db.detailLevel = "minimal" end
  if db.progressView ~= "completionist" then db.progressView = "achievable" end
  if not self:IsID(db.phaseOverride) or db.phaseOverride > 5 then db.phaseOverride = nil end
  for _, field in ipairs({"deferred", "recurringHistory", "acknowledgedChoices", "acknowledgedTurnIns", "completedEvidence"}) do char[field] = flags(char[field]) end
  char.categoryPreferences = self.modules.Selection:Normalize(char.categoryPreferences)
  char.travel = self.modules.Travel:Normalize(char.travel)
  char.discovered = type(char.discovered) == "table" and char.discovered or {}
  for id, value in pairs(char.discovered) do
    if not self:IsID(id) or type(value) ~= "table" or (value.faction~="Alliance" and value.faction~="Horde") then
      char.discovered[id] = nil
    else
      char.discovered[id] = {name=type(value.name)=="string" and string.sub(value.name,1,500) or ("Quest "..id),
        faction=value.faction,level=self:IsID(value.level) and math.min(70,value.level) or 1}
    end
  end
  local intent = type(char.journey) == "table" and char.journey or {mode=char.routeMode, zoneID=char.routeZoneID}
  if not modes[intent.mode] then intent.mode = "journey" end
  if intent.mode == "continue" then intent.mode = "journey" end
  if not self:IsID(intent.zoneID) then intent.zoneID = nil end
  if not self:IsID(intent.questID) then intent.questID = nil end
  if intent.mode == "quest" and not intent.questID then intent.mode = "journey" end
  if (intent.mode == "zone" or intent.mode == "cleanup") and not intent.zoneID then intent.mode = "journey" end
  char.journey = intent
  -- Old route position is only a resume hint, never completion evidence.
  if char.schemaVersion ~= 2 and type(char.routeQuestIDs) == "table" then
    local index = self:IsID(char.routeIndex) and char.routeIndex or 1
    local id = char.routeQuestIDs[index]
    if self:IsID(id) then char.resumeQuestID = id end
  end
  char.routeQuestIDs, char.routeIndex = {}, 1
  char.routeMode = intent.mode
  db.schemaVersion, char.schemaVersion = 2, 2
  MadsTBCLoremasterDB, MadsTBCLoremasterCharacterDB = db, char
  self.db, self.charDB = db, char
end

function Addon:Initialize()
  if self.initialized then return end
  self:NormalizeSavedVariables()
  for _, name in ipairs({"Character", "Eligibility", "Selection", "Planning", "Travel", "Router", "Navigation", "UI"}) do self.modules[name]:Initialize() end
  self.initialized = true
  local _,_,_,interface = GetBuildInfo()
  if interface ~= 20506 then
    self.status = "This build targets TBC Anniversary interface 20506. Client compatibility needs verification."
    self:Emit("STATE_UPDATED", "unsupported_client")
    return
  end
  if Questie and Questie.API and type(Questie.API.RegisterOnReady) == "function" then
    Questie.API.RegisterOnReady(function()
      self.questieReady = true
      self:Rescan("questie_ready")
    end)
    if type(Questie.API.RegisterForQuestUpdates) == "function" then
      Questie.API.RegisterForQuestUpdates(function(id, objective, reason)
        self:Rescan("questie_update", id, objective, reason)
      end)
    end
  else
    self.status = "Questie's readiness API is unavailable. Check that Questie is enabled; this addon may need an API compatibility update."
  end
  self:Emit("STATE_UPDATED", "initialize")
end
function Addon:RecordTurnIn(id)
  if not self.charDB or not self:IsID(id) then return end
  local quest = self:GetQuest(id)
  if quest and not quest.permanent then self.charDB.recurringHistory[id] = true
  else self.charDB.completedEvidence[id] = true end
end
function Addon:Rescan(reason, questID)
  if not self.initialized then return end
  self.dirty = self.dirty or {}
  self.dirty[reason or "event"] = true
  if not self.questieReady or self.scanPending then return end
  self.scanPending = true
  C_Timer.After(0.15, function()
    self.scanPending = nil
    local reasons=self.dirty
    self.dirty = {}
    local ok, ready, changed = pcall(self.modules.Character.Scan, self.modules.Character)
    if not ok or not ready then
      self.status = "Character data is not ready; preserving your journey."
      if not ok and ready ~= self.lastScanError then self.lastScanError = ready; geterrorhandler()(ready) end
      self.retries = (self.retries or 0) + 1
      if self.retries <= 3 then C_Timer.After(self.retries, function() self:Rescan("retry") end) end
      self:Emit("STATE_UPDATED", "waiting")
      return
    end
    self.retries, self.lastScanError, self.status = 0, nil, nil
    local objectiveOnly=true
    for cause in pairs(reasons) do
      if cause~="QUEST_LOG_UPDATE" and cause~="questie_update" then objectiveOnly=false end
    end
    if changed==false and objectiveOnly then return end
    self.modules.Eligibility:Rebuild()
    self.modules.Router:Refresh(reason)
    self:Emit("STATE_UPDATED", reason or "event")
  end)
end
function Addon:GetQuest(id)
  local records = self.modules.Eligibility.records
  return (records and records[id]) or self.Manifest.quests[id]
end
function Addon:SetDetailLevel(level)
  if not ({minimal=true, route=true, arc=true, deep=true})[level] then return end
  self.db.detailLevel = level
  self:Emit("STATE_UPDATED", "detail")
end
function Addon:SetPhaseOverride(phase)
  if phase ~= nil and (not self:IsID(phase) or phase > 5) then return end
  self.db.phaseOverride = phase
  self:Rescan("phase")
end
function Addon:SetProgressView(view)
  if view ~= "completionist" and view ~= "achievable" then return end
  self.db.progressView = view
  self:Emit("STATE_UPDATED", "view")
end

local frame = CreateFrame("Frame")
Addon.eventFrame = frame
frame:SetScript("OnEvent", function(_, event, arg1)
  if event == "ADDON_LOADED" and arg1 == addonName then
    frame:UnregisterEvent("ADDON_LOADED")
    SLASH_MADSTBCLOREMASTER1 = "/mtl"
    SlashCmdList.MADSTBCLOREMASTER = function(message)
      if not Addon.initialized then return end
      message = strtrim(string.lower(message or ""))
      if message == "scan" then Addon:Rescan("manual")
      elseif message == "continue" then Addon.modules.Router:Start("journey")
      elseif message == "catchup" then Addon.modules.Router:Start("catchup")
      elseif message == "track" or message == "back" then Addon.modules.Router:Start("back_on_track")
      elseif message == "leave" then Addon.modules.UI:OpenPlanner("checklist")
      elseif message == "missable" then Addon.modules.UI:OpenPlanner("forecast")
      elseif message == "travel" then Addon.modules.UI:OpenPlanner("travel")
      elseif message == "hide" then Addon.modules.UI:SetTrackerVisible(false)
      elseif message == "show" then Addon.modules.UI:SetTrackerVisible(true)
      elseif message == "toggle" then Addon.modules.UI:ToggleTracker()
      else Addon.modules.UI:Toggle() end
    end
  elseif event == "PLAYER_LOGIN" then
    frame:UnregisterEvent("PLAYER_LOGIN")
    Addon:Initialize()
  elseif Addon.initialized then
    if event=="TAXIMAP_OPENED" then Addon.modules.Travel:ObserveTaxi()
    elseif event=="HEARTHSTONE_BOUND" then Addon.modules.Travel:ObserveBind(true) end
    if event == "QUEST_DETAIL" or event == "QUEST_COMPLETE" then
      local id = GetQuestID and GetQuestID()
      if Addon:IsID(id) then Addon.modules.UI:MaybeWarnChoice(id, event == "QUEST_COMPLETE") end
    else
      if event == "QUEST_TURNED_IN" then Addon:RecordTurnIn(arg1) end
      Addon:Rescan(event, arg1)
    end
  end
end)
for _, event in ipairs({"ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD", "PLAYER_LEVEL_UP", "QUEST_ACCEPTED", "QUEST_REMOVED", "QUEST_TURNED_IN", "QUEST_LOG_UPDATE", "SKILL_LINES_CHANGED", "UPDATE_FACTION", "QUEST_DETAIL", "QUEST_COMPLETE", "SPELLS_CHANGED", "ZONE_CHANGED_NEW_AREA", "ZONE_CHANGED"}) do frame:RegisterEvent(event) end
for _,event in ipairs({"TAXIMAP_OPENED","HEARTHSTONE_BOUND","BAG_UPDATE_COOLDOWN","BAG_UPDATE_DELAYED","PLAYER_CONTROL_GAINED"}) do
  pcall(frame.RegisterEvent,frame,event)
end
