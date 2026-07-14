local Addon = MadsTBC
local Eligibility = {}
Addon:RegisterModule("Eligibility", Eligibility)

local function includesBit(mask, value)
  if not mask or mask == 0 then return true end
  if not value or value == 0 then return false end
  return mask % (value * 2) >= value
end

local function allCompleted(ids, completed)
  for _, questID in ipairs(ids or {}) do
    if not completed[questID] then return false end
  end
  return true
end

local function anyCompleted(ids, completed)
  if not ids or #ids == 0 then return true end
  for _, questID in ipairs(ids) do
    if completed[questID] then return true end
  end
  return false
end

local function scoresForChoice(quest, character)
  local completed = character.completed
  local active = character.active
  if not quest.exclusiveTo or #quest.exclusiveTo == 0 then return true end
  if completed[quest.id] or active[quest.id] then return true end
  local winner = quest
  for _, otherID in ipairs(quest.exclusiveTo) do
    if completed[otherID] or active[otherID] then return false end
    local other = Addon.Manifest.quests[otherID]
    if other then
      local winnerRank = winner.routeOrder or (1000000 + winner.id)
      local otherRank = other.routeOrder or (1000000 + other.id)
      if otherRank < winnerRank then winner = other end
    end
  end
  return winner.id == quest.id
end

local function excludedFromPermanentScore(state)
  return state == "ineligible_faction" or state == "ineligible_race"
    or state == "ineligible_class" or state == "ineligible_profession"
    or state == "temporarily_unavailable" or state == "permanently_locked"
    or state == "unreachable_dependency"
end

local function hasUnreachableDependency(quest, character, memo, visiting)
  local completed = character.completed
  if memo[quest.id] ~= nil then return memo[quest.id] end
  if visiting[quest.id] then return false end
  visiting[quest.id] = true
  local unreachable = false
  for _, questID in ipairs(quest.prerequisitesAll or {}) do
    if not completed[questID] then
      local dependency = Addon.Manifest.quests[questID]
      if not dependency or hasUnreachableDependency(dependency, character, memo, visiting) then
        unreachable = true
        break
      end
    end
  end
  if not unreachable and quest.prerequisitesAny and #quest.prerequisitesAny > 0
    and not anyCompleted(quest.prerequisitesAny, completed) then
    local reachable = false
    for _, questID in ipairs(quest.prerequisitesAny) do
      local dependency = Addon.Manifest.quests[questID]
      if dependency and not hasUnreachableDependency(dependency, character, memo, visiting) then
        reachable = true
        break
      end
    end
    if not reachable then unreachable = true end
  end
  if not unreachable and quest.parentQuest and not completed[quest.parentQuest]
    and not character.active[quest.parentQuest] then
    local dependency = Addon.Manifest.quests[quest.parentQuest]
    if not dependency or hasUnreachableDependency(dependency, character, memo, visiting) then
      unreachable = true
    end
  end
  if not unreachable and quest.enabledBy and not completed[quest.enabledBy] then
    local dependency = Addon.Manifest.quests[quest.enabledBy]
    if not dependency or hasUnreachableDependency(dependency, character, memo, visiting) then
      unreachable = true
    end
  end
  visiting[quest.id] = nil
  memo[quest.id] = unreachable
  return unreachable
end

local function dependencyState(quest, character, memo)
  if hasUnreachableDependency(quest, character, memo, {}) then
    return "unreachable_dependency"
  end
end

local function requiredRanksState(requiredRanks, professions)
  local hasPositive, hasPositiveProfession, meetsPositive = false, false, false
  for _, requirement in ipairs(requiredRanks or {}) do
    local skillID, requiredRank = requirement[1], requirement[2] or 0
    local currentRank = professions[skillID]
    if requiredRank < 0 then
      if currentRank and currentRank >= math.abs(requiredRank) then
        return "permanently_locked"
      end
    else
      hasPositive = true
      if currentRank then
        hasPositiveProfession = true
        if currentRank >= requiredRank then meetsPositive = true end
      end
    end
  end
  if hasPositive and not meetsPositive then
    return hasPositiveProfession and "blocked_profession" or "ineligible_profession"
  end
end

local function reputationValue(character, factionID)
  local reputation = character.reputations[factionID]
  if reputation then return reputation.value end
  if Eligibility.factionsStartingBelowNeutral
    and Eligibility.factionsStartingBelowNeutral[factionID] then
    return -36000
  end
  return 0
end

function Eligibility:Initialize()
  self.states = {}
  self.scoredChoices = {}
  self.zones = {}
  self.summary = {}
  self.factionsStartingBelowNeutral = nil
  if QuestieLoader then
    local ok, reputation = pcall(function() return QuestieLoader:ImportModule("QuestieReputation") end)
    if ok and reputation then
      self.factionsStartingBelowNeutral = reputation.factionsStartingBelowNeutral
    end
  end
end

function Eligibility:Classify(quest, character)
  local completed = character.completed
  if completed[quest.id] then return "completed" end
  if character.faction ~= "Alliance" then return "ineligible_faction" end
  if not includesBit(quest.requiredRaces, character.raceMask) then return "ineligible_race" end
  if not includesBit(quest.requiredClasses, character.classMask) then return "ineligible_class" end
  local active = character.active[quest.id]
  if active then return active.complete and "ready_to_turn_in" or "active" end
  local activePhase = Addon.db.phaseOverride or Addon.Manifest.phase.number
  if quest.availablePhase and quest.availablePhase > activePhase and not active then return "temporarily_unavailable" end
  if quest.phaseStatus == "future" and not quest.availablePhase and not active then return "temporarily_unavailable" end
  if quest.eventOnly and not active then return "temporarily_unavailable_event" end
  if quest.maximumLevel and character.level > quest.maximumLevel then return "permanently_locked" end
  if quest.disabledBy and character.active[quest.disabledBy] then return "temporarily_unavailable" end
  if quest.breadcrumbFor
    and (completed[quest.breadcrumbFor] or character.active[quest.breadcrumbFor]) then
    return "permanently_locked"
  end
  for _, conflict in ipairs(quest.exclusiveTo or {}) do
    if completed[conflict] or character.active[conflict] then return "permanently_locked" end
  end
  if quest.requiredSkill then
    local skillID, minimumRank = quest.requiredSkill[1], quest.requiredSkill[2] or 1
    local currentRank = character.professions[skillID]
    if not currentRank then return "ineligible_profession" end
    if currentRank < minimumRank then return "blocked_profession" end
  end
  if quest.requiredSpell and quest.requiredSpell ~= 0 and IsSpellKnown then
    local known = IsSpellKnown(math.abs(quest.requiredSpell))
    if quest.requiredSpell > 0 and not known then return "blocked_profession" end
    if quest.requiredSpell < 0 and known then return "permanently_locked" end
  end
  local rankState = requiredRanksState(quest.requiredRanks, character.professions)
  if rankState then return rankState end
  if quest.requiredMinRep then
    local value = reputationValue(character, quest.requiredMinRep[1])
    if value < quest.requiredMinRep[2] then return "blocked_reputation" end
  end
  if quest.requiredMaxRep then
    local value = reputationValue(character, quest.requiredMaxRep[1])
    if value >= quest.requiredMaxRep[2] then return "permanently_locked" end
  end
  local dependency = dependencyState(quest, character, self.unreachableDependencies or {})
  if dependency then return dependency end
  if character.level < (quest.requiredLevel or 0) then return "level_locked" end
  if not allCompleted(quest.prerequisitesAll, completed) then return "prerequisite_blocked" end
  if not anyCompleted(quest.prerequisitesAny, completed) then return "prerequisite_blocked" end
  if quest.parentQuest and not completed[quest.parentQuest] and not character.active[quest.parentQuest] then return "prerequisite_blocked" end
  if quest.enabledBy and not completed[quest.enabledBy] then return "prerequisite_blocked" end
  return "available"
end

function Eligibility:Rebuild()
  local character = Addon.modules.Character.snapshot
  local zones = {}
  local summary = {
    permanentCompleted = 0, permanentTotal = 0,
    recurringCurrent = 0, recurringAvailable = 0, recurringLifetime = 0,
    available = 0, blocked = 0, locked = 0, alternatives = 0,
  }
  self.states = {}
  self.scoredChoices = {}
  self.unreachableDependencies = {}
  for questID, quest in pairs(Addon.Manifest.quests) do
    local state = self:Classify(quest, character)
    self.states[questID] = state
    local zone = zones[quest.canonicalZone] or {
      id = quest.canonicalZone, name = quest.zoneName, completed = 0, total = 0,
      available = 0, actionable = 0, blocked = 0, locked = 0, recurring = 0,
      geographic = false,
    }
    zones[quest.canonicalZone] = zone
    if quest.geographic then zone.geographic = true end
    if quest.permanent then
      self.scoredChoices[questID] = scoresForChoice(quest, character)
      local countsForScore = not excludedFromPermanentScore(state) and self.scoredChoices[questID]
      if not excludedFromPermanentScore(state) then
        if self.scoredChoices[questID] then
          zone.total = zone.total + 1
          summary.permanentTotal = summary.permanentTotal + 1
          if state == "completed" then
            zone.completed = zone.completed + 1
            summary.permanentCompleted = summary.permanentCompleted + 1
          end
        else
          summary.alternatives = summary.alternatives + 1
        end
      elseif state == "permanently_locked" or state == "unreachable_dependency" then
        zone.locked = zone.locked + 1
        summary.locked = summary.locked + 1
      end
      if countsForScore then
        if state == "available" or state == "active" or state == "ready_to_turn_in" then
          zone.available = zone.available + 1
          summary.available = summary.available + 1
          if quest.geographic then zone.actionable = zone.actionable + 1 end
        elseif string.find(state, "blocked", 1, true) or state == "level_locked" then
          zone.blocked = zone.blocked + 1
          summary.blocked = summary.blocked + 1
        end
      end
    else
      zone.recurring = zone.recurring + 1
      if state == "completed" then summary.recurringCurrent = summary.recurringCurrent + 1 end
      if state == "available" or state == "active" or state == "ready_to_turn_in" or state == "completed" then
        summary.recurringAvailable = summary.recurringAvailable + 1
      end
      if Addon.charDB.recurringHistory[questID] then summary.recurringLifetime = summary.recurringLifetime + 1 end
    end
  end
  self.zones = zones
  self.summary = summary
end

function Eligibility:GetState(questID)
  return self.states[questID]
end

function Eligibility:IsRoutable(questID, includeBlocked)
  local state = self.states[questID]
  return state == "available" or state == "active" or state == "ready_to_turn_in"
    or (includeBlocked and (state == "prerequisite_blocked" or state == "level_locked"))
end

function Eligibility:IsRecommendedChoice(questID)
  return self.scoredChoices[questID] ~= false
end
