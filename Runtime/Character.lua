local Addon = MadsTBC
local Character = {}
Addon:RegisterModule("Character", Character)

local function questLogSnapshot()
  local active = {}
  local count = C_QuestLog and C_QuestLog.GetNumQuestLogEntries and C_QuestLog.GetNumQuestLogEntries() or GetNumQuestLogEntries()
  for index = 1, count do
    local info
    if C_QuestLog and C_QuestLog.GetInfo then info = C_QuestLog.GetInfo(index) end
    local questID = info and info.questID
    local isHeader = info and info.isHeader
    if not info then
      local _, _, _, header, _, complete, _, id = GetQuestLogTitle(index)
      questID, isHeader = id, header
      if questID and not isHeader then active[questID] = {complete = complete == 1} end
    elseif questID and not isHeader then
      local complete = C_QuestLog.IsComplete and C_QuestLog.IsComplete(questID)
      active[questID] = {complete = complete and true or false}
    end
  end
  return active
end

local function completedSnapshot()
  if GetQuestsCompleted then return GetQuestsCompleted() or {} end
  local result = {}
  local ids = C_QuestLog and C_QuestLog.GetAllCompletedQuestIDs and C_QuestLog.GetAllCompletedQuestIDs()
  for _, questID in ipairs(ids or {}) do result[questID] = true end
  return result
end

local function professionSnapshot()
  local result = {}
  -- Questie's skill-line snapshot includes skills such as Riding that are not
  -- returned by GetProfessions, but are used by requiredRanks quest gates.
  if QuestieLoader then
    local ok, professions = pcall(function()
      local module = QuestieLoader:ImportModule("QuestieProfessions")
      return module and module:GetPlayerProfessions()
    end)
    if ok then
      for skillID, profession in pairs(professions or {}) do
        if type(profession) == "table" then result[skillID] = profession[2] or 0 end
      end
    end
  end
  if not GetProfessions or not GetProfessionInfo then return result end
  -- GetProfessions has nil holes (for example a character with Cooking and
  -- Fishing but no primary professions), so ipairs would stop before the
  -- secondary-profession slots.
  local indices = {GetProfessions()}
  for slot = 1, 6 do
    local index = indices[slot]
    if index then
      local _, _, rank, _, _, _, skillLine = GetProfessionInfo(index)
      if skillLine then result[skillLine] = rank or 0 end
    end
  end
  return result
end

local function reputationSnapshot()
  local result = {}
  if not GetNumFactions or not GetFactionInfo then return result end
  if ExpandFactionHeader then ExpandFactionHeader(0) end
  for index = 1, GetNumFactions() do
    local _, _, standingID, _, _, barValue, _, _, isHeader, _, _, _, _, factionID = GetFactionInfo(index)
    if factionID and not isHeader then
      result[factionID] = {standing = standingID or 0, value = barValue or 0}
    end
  end
  return result
end

local function currentAreaID()
  local uiMapID = C_Map and C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")
  if not uiMapID then return nil end
  if QuestieLoader then
    local ok, zoneDB = pcall(function() return QuestieLoader:ImportModule("ZoneDB") end)
    if ok and zoneDB and zoneDB.GetAreaIdByUiMapId then
      local mappedOK, areaID = pcall(zoneDB.GetAreaIdByUiMapId, zoneDB, uiMapID)
      if mappedOK and areaID and areaID > 0 then return areaID end
    end
  end
  return uiMapID
end

function Character:Initialize()
  self.snapshot = self.snapshot or {}
end

function Character:Scan()
  local _, raceToken, raceID = UnitRace("player")
  local _, classToken, classID = UnitClass("player")
  self.snapshot = {
    faction = UnitFactionGroup("player"),
    raceToken = raceToken,
    raceID = raceID,
    raceMask = raceID and 2 ^ (raceID - 1) or 0,
    classToken = classToken,
    classID = classID,
    classMask = classID and 2 ^ (classID - 1) or 0,
    level = UnitLevel("player") or 1,
    currentAreaID = currentAreaID(),
    completed = completedSnapshot(),
    active = questLogSnapshot(),
    professions = professionSnapshot(),
    reputations = reputationSnapshot(),
  }
  for questID in pairs(self.snapshot.completed) do
    local quest = Addon.Manifest.quests[questID]
    if quest and not quest.permanent then Addon.charDB.recurringHistory[questID] = true end
  end
  return self.snapshot
end

function Character:IsCompleted(questID)
  return self.snapshot.completed and self.snapshot.completed[questID] or false
end

function Character:IsActive(questID)
  return self.snapshot.active and self.snapshot.active[questID]
end
