local Addon = MadsTBC
local Router = {}
Addon:RegisterModule("Router", Router)

local ROUTE_PLAN_VERSION = 4

local modeLabels = {
  ["continue"] = "Continue Journey",
  ["catchup"] = "Catch Up on What You Missed",
  ["back_on_track"] = "Get Back on Track",
  ["zone"] = "Zone Sweep",
}

local function routeRank(quest)
  if quest.routeOrder then return quest.routeOrder end
  return 100000 + (quest.requiredLevel or 0) * 100 + (quest.id % 100)
end

local function effectiveQuestLevel(quest)
  local required = quest.requiredLevel or 0
  local listed = quest.questLevel
  -- Questie uses -1 for several battleground and repeatable quests. It means
  -- "no normal quest level", not "a quest below every player level".
  if not listed or listed < 0 then listed = required end
  return math.max(required, listed)
end

local function questSort(a, b)
  if a.canonicalZone ~= b.canonicalZone then
    local az = a.zoneName or ""
    local bz = b.zoneName or ""
    if az ~= bz then return az < bz end
    return a.canonicalZone < b.canonicalZone
  end
  if routeRank(a) ~= routeRank(b) then return routeRank(a) < routeRank(b) end
  return a.id < b.id
end

local function appendDependencies(quest, result, seen)
  if seen[quest.id] then return end
  seen[quest.id] = true
  local completed = Addon.modules.Character.snapshot.completed
  for _, dependency in ipairs(quest.prerequisitesAll or {}) do
    local prerequisite = Addon.Manifest.quests[dependency]
    if prerequisite and not completed[dependency] then appendDependencies(prerequisite, result, seen) end
  end
  if quest.prerequisitesAny and #quest.prerequisitesAny > 0 then
    local satisfied = false
    for _, dependency in ipairs(quest.prerequisitesAny) do
      if completed[dependency] then satisfied = true break end
    end
    if not satisfied then
      for _, dependency in ipairs(quest.prerequisitesAny) do
        local prerequisite = Addon.Manifest.quests[dependency]
        if prerequisite and Addon.modules.Eligibility:IsRoutable(dependency, true) then
          appendDependencies(prerequisite, result, seen)
          break
        end
      end
    end
  end
  if quest.enabledBy and not completed[quest.enabledBy] then
    local prerequisite = Addon.Manifest.quests[quest.enabledBy]
    if prerequisite then appendDependencies(prerequisite, result, seen) end
  end
  if not completed[quest.id] then table.insert(result, quest) end
end

function Router:Initialize()
  self.plan = {}
  self.index = Addon.charDB.routeIndex or 1
  if Addon.charDB.routeQuestIDs and #Addon.charDB.routeQuestIDs > 0 then
    for _, questID in ipairs(Addon.charDB.routeQuestIDs) do
      if Addon.Manifest.quests[questID] then table.insert(self.plan, questID) end
    end
  end
end

function Router:_SetNavigation(questID)
  local ok, message = pcall(Addon.modules.Navigation.SetForQuest, Addon.modules.Navigation, questID)
  if not ok and message ~= self.lastNavigationError then
    self.lastNavigationError = message
    Addon:Print("Waypoint update failed; the route tracker will continue without it. " .. tostring(message))
  elseif ok then
    self.lastNavigationError = nil
  end
end

function Router:_BelongsInPlan(questID, state)
  if state == "completed" or Addon.charDB.deferred[questID] then return false end
  if Addon.charDB.routeMode == "catchup" and state == "level_locked" then return false end
  return Addon.modules.Eligibility:IsRoutable(questID, true)
end

function Router:_Candidates(includeBlocked, permanentOnly)
  local result = {}
  for questID, quest in pairs(Addon.Manifest.quests) do
    if not Addon.charDB.deferred[questID]
      and (not permanentOnly or quest.permanent)
      and Addon.modules.Eligibility:IsRecommendedChoice(questID)
      and Addon.modules.Eligibility:IsRoutable(questID, includeBlocked) then
      table.insert(result, quest)
    end
  end
  return result
end

function Router:Build(mode, zoneID)
  local level = Addon.modules.Character.snapshot.level
  local candidates = self:_Candidates(true, true)
  local selected = {}
  if mode == "zone" and zoneID then
    for _, quest in ipairs(candidates) do
      if quest.canonicalZone == zoneID then table.insert(selected, quest) end
    end
  elseif mode == "catchup" then
    for _, quest in ipairs(candidates) do
      local state = Addon.modules.Eligibility:GetState(quest.id)
      if state ~= "level_locked" and (quest.requiredLevel or 0) <= level
        and effectiveQuestLevel(quest) < level then
        table.insert(selected, quest)
      end
    end
  elseif mode == "back_on_track" then
    local frontier
    table.sort(candidates, function(a, b)
      local ad = math.abs((a.requiredLevel or 0) - level)
      local bd = math.abs((b.requiredLevel or 0) - level)
      if ad ~= bd then return ad < bd end
      return routeRank(a) < routeRank(b)
    end)
    frontier = candidates[1]
    if frontier then
      for _, quest in ipairs(candidates) do
        if quest.canonicalZone == frontier.canonicalZone and (quest.requiredLevel or 0) <= level + 2 then
          table.insert(selected, quest)
        end
      end
    end
  else
    local frontier
    table.sort(candidates, function(a, b)
      local aReady = (a.requiredLevel or 0) <= level + 2
      local bReady = (b.requiredLevel or 0) <= level + 2
      if aReady ~= bReady then return aReady end
      return routeRank(a) < routeRank(b)
    end)
    frontier = candidates[1]
    if frontier then
      for _, quest in ipairs(candidates) do
        if quest.canonicalZone == frontier.canonicalZone and (quest.requiredLevel or 0) <= level + 2 then
          table.insert(selected, quest)
        end
      end
    end
  end
  local currentAreaID = Addon.modules.Character.snapshot.currentAreaID
  table.sort(selected, function(a, b)
    if mode == "catchup" and currentAreaID then
      local aLocal = a.canonicalZone == currentAreaID
      local bLocal = b.canonicalZone == currentAreaID
      if aLocal ~= bLocal then return aLocal end
    end
    return questSort(a, b)
  end)
  local expanded, seen = {}, {}
  for _, quest in ipairs(selected) do appendDependencies(quest, expanded, seen) end
  local ids = {}
  for _, quest in ipairs(expanded) do
    local state = Addon.modules.Eligibility:GetState(quest.id)
    local levelAppropriate = mode ~= "catchup"
      or (state ~= "level_locked" and (quest.requiredLevel or 0) <= level)
    if state ~= "completed" and levelAppropriate
      and Addon.modules.Eligibility:IsRoutable(quest.id, true) then
      table.insert(ids, quest.id)
    end
  end
  return ids
end

function Router:Start(mode, zoneID)
  self.plan = self:Build(mode, zoneID)
  self.index = 1
  Addon.charDB.routeMode = mode
  Addon.charDB.routeQuestIDs = self.plan
  Addon.charDB.routeIndex = 1
  Addon.charDB.routePlanVersion = ROUTE_PLAN_VERSION
  Addon.charDB.routeZoneID = zoneID
  Addon.charDB.firstScanComplete = true
  if #self.plan == 0 then
    Addon:Print("No recoverable quests currently match that route.")
  else
    Addon:Print(modeLabels[mode] .. " started with " .. #self.plan .. " quests.")
  end
  self:_SetNavigation(self.plan[1])
  Addon:Emit("STATE_UPDATED", "route")
end

function Router:Refresh()
  if not self.plan then return end
  -- Rebuild routes saved by an older selector. This repairs existing Catch Up
  -- plans immediately after /reload instead of making the player recreate one.
  if Addon.charDB.routeMode and Addon.charDB.routePlanVersion ~= ROUTE_PLAN_VERSION then
    self.plan = self:Build(Addon.charDB.routeMode, Addon.charDB.routeZoneID)
    self.index = 1
    Addon.charDB.routeQuestIDs = self.plan
    Addon.charDB.routeIndex = 1
    Addon.charDB.routePlanVersion = ROUTE_PLAN_VERSION
  end
  -- Compact all remaining steps on every rescan. This keeps both the current
  -- step and the displayed route total synchronized with changing eligibility.
  local compacted = {}
  for position = self.index, #self.plan do
    local questID = self.plan[position]
    local state = Addon.modules.Eligibility:GetState(questID)
    if self:_BelongsInPlan(questID, state) then table.insert(compacted, questID) end
  end
  self.plan = compacted
  self.index = 1
  Addon.charDB.routeQuestIDs = self.plan
  Addon.charDB.routeIndex = 1
  self:_SetNavigation(self.plan[1])
end

function Router:GetCurrent()
  if not self.plan or self.index > #self.plan then return nil end
  local questID = self.plan[self.index]
  local quest = Addon.Manifest.quests[questID]
  if not quest then return nil end
  return quest, Addon.modules.Eligibility:GetState(questID), self.index, #self.plan
end

function Router:DescribeStep(quest, state)
  if state == "ready_to_turn_in" then
    return "Turn in " .. quest.name .. (quest.finisher and quest.finisher.name and " to " .. quest.finisher.name or "")
  elseif state == "active" then
    return "Complete " .. quest.name
  elseif state == "level_locked" then
    return "Reach level " .. (quest.requiredLevel or 0) .. " for " .. quest.name
  elseif state == "prerequisite_blocked" then
    return "Complete the prerequisite chain for " .. quest.name
  elseif state == "blocked_profession" then
    return "Meet the profession requirement for " .. quest.name
  elseif state == "blocked_reputation" then
    return "Meet the reputation requirement for " .. quest.name
  end
  return "Accept " .. quest.name .. (quest.starter and quest.starter.name and " from " .. quest.starter.name or "")
end

function Router:DeferCurrent()
  local quest = self:GetCurrent()
  if not quest then return end
  Addon.charDB.deferred[quest.id] = true
  self.index = self.index + 1
  Addon.charDB.routeIndex = self.index
  self:Refresh()
  Addon:Emit("STATE_UPDATED", "defer")
end

function Router:ModeLabel()
  return modeLabels[Addon.charDB.routeMode] or "No route selected"
end
