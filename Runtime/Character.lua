local Addon = MadsTBC
local Character = {}
Addon:RegisterModule("Character", Character)

local function completedSnapshot()
  local result = {}
  if GetQuestsCompleted then
    local values = GetQuestsCompleted()
    if type(values) ~= "table" then return nil end
    for id, value in pairs(values) do if Addon:IsID(id) and value then result[id] = true end end
  elseif C_QuestLog and C_QuestLog.GetAllCompletedQuestIDs then
    local ids = C_QuestLog.GetAllCompletedQuestIDs()
    if type(ids) ~= "table" then return nil end
    for _, id in ipairs(ids) do if Addon:IsID(id) then result[id] = true end end
  else return nil end
  for id in pairs(Addon.charDB.completedEvidence) do result[id] = true end
  return result
end
local function questLogSnapshot()
  local active, used = {}, 0
  local count = C_QuestLog and C_QuestLog.GetNumQuestLogEntries and C_QuestLog.GetNumQuestLogEntries()
  if count == nil and GetNumQuestLogEntries then count = GetNumQuestLogEntries() end
  if not Addon:IsNumber(count) or count < 0 then return nil end
  for index = 1, count do
    local info = C_QuestLog and C_QuestLog.GetInfo and C_QuestLog.GetInfo(index)
    if not info and GetQuestLogTitle then
      local title, level, _, header, _, complete, _, id = GetQuestLogTitle(index)
      if title then info = {title=title, level=level, isHeader=header, questID=id, complete=complete == 1, failed=complete == -1} end
    end
    if not info then return nil end
    if not info.isHeader then
      local id = info.questID
      if not Addon:IsID(id) then return nil end
      local complete = info.complete
      if C_QuestLog and C_QuestLog.IsComplete then complete = C_QuestLog.IsComplete(id) end
      local failed = info.failed
      -- The pinned TBC QuestLogCache uses the sixth legacy return for failure.
      -- Only merge it when the row still identifies this exact quest.
      if GetQuestLogTitle then
        local _, _, _, _, _, legacyComplete, _, legacyID = GetQuestLogTitle(index)
        if legacyID == id then failed = legacyComplete == -1 end
      end
      local objectives = C_QuestLog and C_QuestLog.GetQuestObjectives and C_QuestLog.GetQuestObjectives(id)
      active[id] = {complete=not failed and (complete == true or complete == 1), failed=failed,
        -- Client/dependency tables can be reused and mutated between events.
        -- Own the snapshot so equality still detects objective-only changes.
        objectives=type(objectives) == "table" and Addon:Copy(objectives) or nil, title=info.title, level=info.level, logIndex=index}
      used = used + 1
    end
  end
  return active, used
end
local function professionSnapshot()
  local result, ready = {}, false
  local module = Addon:Import("QuestieProfessions")
  if module and module.GetPlayerProfessions then
    local ok, values = pcall(module.GetPlayerProfessions, module)
    if ok and type(values) == "table" then
      ready = true
      for id, value in pairs(values) do
        if type(value) == "table" and Addon:IsNumber(value[2]) then result[id] = value[2] end
      end
    end
  end
  if GetProfessions and GetProfessionInfo then
    local indices = {GetProfessions()}
    for slot = 1, 6 do
      if indices[slot] then
        local _, _, rank, _, _, _, skillID = GetProfessionInfo(indices[slot])
        if skillID then result[skillID] = rank or 0 end
      end
    end
    -- Riding still requires Questie's skill-line data.
  end
  return result, ready
end
local function reputationSnapshot()
  -- Read the ready dependency's snapshot. Never expand the user's faction UI.
  local result = {}
  local module = Addon:Import("QuestieReputation")
  if module and module.GetPlayerReputations then
    local ok, values = pcall(module.GetPlayerReputations, module)
    if ok and type(values) == "table" then
      for id, value in pairs(values) do
        if type(value) == "table" then result[id] = {standing=value[1], value=value[2]} end
      end
      return result, true, module.factionsStartingBelowNeutral
    end
  end
  return result, false, nil
end
local function currentAreaID()
  local map = C_Map and C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")
  local db = Addon:Import("ZoneDB")
  if map and db and db.GetAreaIdByUiMapId then
    local ok, id = pcall(db.GetAreaIdByUiMapId, db, map)
    if ok and Addon:IsID(id) then return id, map end
  end
  return nil, map
end
local function equal(a,b)
  if type(a)~=type(b) then return false end
  if type(a)~="table" then return a==b end
  for k,v in pairs(a) do if k~="generation" and not equal(v,b[k]) then return false end end
  for k in pairs(b) do if k~="generation" and a[k]==nil then return false end end
  return true
end
function Character:Initialize() self.snapshot = {} end
function Character:Scan()
  local _, race, raceID = UnitRace("player")
  local _, class, classID = UnitClass("player")
  local faction, level = UnitFactionGroup("player"), UnitLevel("player")
  local completed = completedSnapshot()
  local active, used = questLogSnapshot()
  if not completed or not active or not raceID or not classID or not level or level < 1
    or (faction ~= "Alliance" and faction ~= "Horde") then return false end
  local professions, professionsReady = professionSnapshot()
  local reputations, reputationsReady, belowNeutral = reputationSnapshot()
  local area, map = currentAreaID()
  local maximum = C_QuestLog and C_QuestLog.GetMaxNumQuestsCanAccept and C_QuestLog.GetMaxNumQuestsCanAccept()
  local snapshot = {ready=true, generation=(self.snapshot.generation or 0)+1,
    faction=faction, raceToken=race, raceID=raceID, raceMask=2^(raceID-1),
    classToken=class, classID=classID, classMask=2^(classID-1), level=level,
    currentAreaID=area, uiMapID=map, completed=completed, active=active, logUsed=used,
    logMaximum=Addon:IsID(maximum) and maximum or 25, logMaximumObserved=Addon:IsID(maximum),
    professions=professions, professionsReady=professionsReady, reputations=reputations,
    reputationsReady=reputationsReady, belowNeutral=belowNeutral or {}}
  local event=Addon:Import("QuestieEvent")
  snapshot.events=event and {ready=event.calendarDataCached,active=Addon:Copy(event.activeQuests or {})} or {}
  local changed=not equal(snapshot,self.snapshot)
  if changed then self.snapshot=snapshot end
  for id in pairs(completed) do
    local quest = Addon:GetQuest(id)
    if quest and not quest.permanent then Addon.charDB.recurringHistory[id] = true end
  end
  for id, info in pairs(active) do
    if not Addon.Manifest.quests[id] then
      Addon.charDB.discovered[id] = {name=info.title or ("Quest " .. id), faction=faction, level=info.level}
    end
  end
  return true,changed
end
function Character:IsCompleted(id) return self.snapshot.completed and self.snapshot.completed[id] or false end
function Character:IsActive(id) return self.snapshot.active and self.snapshot.active[id] end
