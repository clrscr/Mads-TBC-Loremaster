local Addon = MadsTBC
local Eligibility = {}
Addon:RegisterModule("Eligibility", Eligibility)
local possible = {available=true, active=true, ready_to_turn_in=true, prerequisite_blocked=true,
  level_locked=true, blocked_profession=true, blocked_reputation=true}
local function bit(mask, value)
  return not mask or mask == 0 or (value and value > 0 and mask % (value*2) >= value)
end
local function intersects(a, b)
  if not a or a == 0 then return true end
  local value = 1
  while value <= 1024 do
    if bit(a, value) and bit(b, value) then return true end
    value = value * 2
  end
  return false
end
function Eligibility:Initialize()
  self.states, self.results, self.zones, self.summary = {}, {}, {}, {}
end
function Eligibility:InFaction(q)
  local faction = Addon.modules.Character.snapshot.faction
  if q.observedFaction then return q.observedFaction == faction end
  return intersects(q.requiredRaces, faction == "Alliance" and 1101 or 690)
end
function Eligibility:CompletedOnce(id)
  local q = self.records[id]
  return Addon.modules.Character:IsCompleted(id) or (q and not q.permanent and Addon.charDB.recurringHistory[id]) or false
end
function Eligibility:ResolveRecords()
  local c = Addon.modules.Character.snapshot
  local context = c.faction .. ":" .. c.classToken .. ":" .. (c.raceToken == "Human" and "Human" or "Other")
  if self.context ~= context then
    self.context, self.records = context, {}
    for id, raw in pairs(Addon.Manifest.quests) do
      local record = raw
      for _, variant in ipairs(raw.variants or {}) do
        for _, candidate in ipairs(variant.contexts) do
          if context == candidate then
            record = Addon:Copy(raw)
            for key, value in pairs(variant.fields) do record[key] = value end
            for _, key in ipairs(variant.clear) do record[key] = nil end
          end
        end
      end
      self.records[id] = record
    end
    self.conflicts, self.children, self.groups = {}, {}, {}
    for id, q in pairs(self.records) do
      self.conflicts[id] = self.conflicts[id] or {}
      for _, other in ipairs(q.exclusiveTo or {}) do
        self.conflicts[id][other] = true
        self.conflicts[other] = self.conflicts[other] or {}
        self.conflicts[other][id] = true
      end
      if q.parentQuest then
        self.children[q.parentQuest] = self.children[q.parentQuest] or {}
        table.insert(self.children[q.parentQuest], id)
      end
    end
    -- Some source child associations intentionally omit an active-parent gate
    -- (for example a repeatable interaction). Preserve the association without
    -- inventing a parentQuest eligibility restriction on the child.
    for id,q in pairs(self.records) do
      for _,child in ipairs(q.children or {}) do
        self.children[id]=self.children[id] or {}
        local found=false
        for _,existing in ipairs(self.children[id]) do if existing==child then found=true; break end end
        if not found then table.insert(self.children[id],child) end
      end
    end
    for _, children in pairs(self.children) do table.sort(children) end
    -- Reverse only explicit requirements; a relation is not an availability claim.
    self.followUps = {}
    for id, q in pairs(self.records) do
      local requirements = {}
      for _, group in ipairs(self:RequirementGroups(q)) do
        for _, prerequisite in ipairs(group) do requirements[prerequisite] = true end
      end
      if q.parentQuest then requirements[q.parentQuest] = true end
      if q.enabledBy then requirements[q.enabledBy] = true end
      for prerequisite in pairs(requirements) do
        self.followUps[prerequisite] = self.followUps[prerequisite] or {}
        table.insert(self.followUps[prerequisite], id)
      end
    end
    for _, ids in pairs(self.followUps) do table.sort(ids) end
  end
  for id, info in pairs(Addon.charDB.discovered) do
    if not self.records[id] then
      self.records[id] = {id=id, name=type(info.name)=="string" and info.name or ("Quest "..id),
        canonicalZone=0, zoneName="Uncatalogued", requiredLevel=1, questLevel=info.level or 1,
        permanent=true, category="unknown", observedFaction=info.faction, unknownAvailability=true}
    end
  end
end
-- Questie IsPreQuestGroupFulfilled: positive group entries accept the source's
-- exclusive equivalents; negative entries require the exact quest. Singles win
-- when both fields exist. Keep this separate from routing exclusivity.
function Eligibility:RequirementGroups(q)
  self.groups = self.groups or {}
  if self.groups[q.id] then return self.groups[q.id] end
  local groups = {}
  if q.prerequisitesAny and #q.prerequisitesAny > 0 then
    groups[1] = q.prerequisitesAny
  else
    for _, id in ipairs(q.prerequisitesAll or {}) do
      local group = {math.abs(id)}
      local dependency = self.records[id]
      if id > 0 and dependency then
        for _, alternative in ipairs(dependency.exclusiveTo or {}) do table.insert(group,alternative) end
      end
      table.insert(groups,group)
    end
  end
  self.groups[q.id] = groups
  return groups
end
function Eligibility:Classify(q, c, visiting)
  if self.results[q.id] then return self.results[q.id].state end
  visiting = visiting or {}
  local function done(state, reason, blocker)
    visiting[q.id] = nil
    self.results[q.id] = {state=state, reason=reason, blocker=blocker}
    return state
  end
  if not q.permanent and c.active[q.id] then
    return done(c.active[q.id].complete and "ready_to_turn_in" or "active", "Recurring quest in your log; its first completion remains recorded.")
  end
  if c.completed[q.id] then return done("completed", "Confirmed by Blizzard completion evidence.") end
  if not self:InFaction(q) then return done("ineligible_faction", "Quest belongs to the other faction.") end
  if not bit(q.requiredRaces, c.raceMask) then return done("ineligible_race", "Requires another race.") end
  if not bit(q.requiredClasses, c.classMask) then return done("ineligible_class", "Requires another class.") end
  local active = c.active[q.id]
  if active then return done(active.complete and "ready_to_turn_in" or "active", active.failed and "Quest failed; inspect the quest log before retrying." or "In your quest log.") end
  if visiting[q.id] then return "unknown_dependency" end
  visiting[q.id] = true
  local phase = Addon.db.phaseOverride or Addon.Manifest.phase.number
  local phaseState = q.availabilityByPhase and q.availabilityByPhase[phase]
  if phaseState == "future" or (q.availablePhase and q.availablePhase > phase) then return done("temporarily_unavailable", "Not released in the selected phase.") end
  if phaseState == "unavailable" then return done("unknown_availability", "Source marks this quest unavailable in the selected phase.") end
  if q.eventOnly or phaseState == "event" then
    local event = Addon:Import("QuestieEvent")
    local ok, available = false, false
    if event and event.calendarDataCached ~= false and event.IsEventActiveForQuest then ok, available = pcall(event.IsEventActiveForQuest, q.id) end
    if not ok then return done("unknown_availability", "Event availability is unknown.") end
    if not available then return done("temporarily_unavailable_event", "The event is not currently active in Questie's snapshot.") end
  end
  if q.nextQuest and (c.completed[q.nextQuest] or c.active[q.nextQuest]) then
    return done(c.completed[q.nextQuest] and "permanently_locked" or "temporarily_unavailable", "The next quest in the chain supersedes this opportunity.", q.nextQuest)
  end
  if q.maximumLevel and c.level > q.maximumLevel then return done("permanently_locked", "Exceeded the quest's maximum level.") end
  if q.availableUntilCompleted and c.completed[q.availableUntilCompleted] then return done("permanently_locked", "A later quest closed this opportunity.", q.availableUntilCompleted) end
  if q.breadcrumbFor and (c.completed[q.breadcrumbFor] or c.active[q.breadcrumbFor]) then
    return done(c.completed[q.breadcrumbFor] and "permanently_locked" or "temporarily_unavailable", "The destination quest supersedes this breadcrumb.", q.breadcrumbFor)
  end
  if q.disabledBy and c.active[q.disabledBy] then return done("temporarily_unavailable", "Another active quest prevents this quest.", q.disabledBy) end
  for other in pairs(self.conflicts[q.id] or {}) do
    if c.completed[other] or c.active[other] then return done(c.completed[other] and "permanently_locked" or "temporarily_unavailable", "Conflicts with another outcome.", other) end
  end
  local localState, localReason
  if q.requiredSkill or q.requiredRanks then
    if not c.professionsReady then return done("unknown_requirement", "Profession data is not ready.") end
    if q.requiredSkill then
      local rank = c.professions[q.requiredSkill[1]]
      if not rank then return done("ineligible_profession", "Requires a profession this character has not learned.") end
      if rank < (q.requiredSkill[2] or 1) then localState,localReason="blocked_profession", "Increase the required profession rank." end
    end
    if q.requiredRanks and #q.requiredRanks>0 then
      -- Questie's signed tier indices refer to trained spells. Skill points
      -- cannot distinguish a capped Journeyman from a trained Expert.
      local professions=Addon:Import("QuestieProfessions")
      if not professions or type(professions.HasProfessionAndRankLevel)~="function" then
        return done("unknown_requirement", "Trained profession rank data is unavailable.")
      end
      local ok,learned,meets,negative=pcall(professions.HasProfessionAndRankLevel,professions,q.requiredRanks)
      if not ok or type(learned)~="boolean" or type(meets)~="boolean" or type(negative)~="boolean" then
        return done("unknown_requirement", "Trained profession rank data is unavailable.")
      end
      if negative then
        if learned and not meets then return done("permanently_locked", "A trained profession rank closes this quest opportunity.") end
      elseif not learned then return done("ineligible_profession", "Requires a profession this character has not learned.")
      elseif not meets then localState,localReason="blocked_profession", "Train the required profession rank." end
    end
  end
  if q.requiredSpecialization then return done("unknown_requirement", "Specialization requirement needs verification.") end
  if q.requiredSpell and q.requiredSpell ~= 0 then
    if not IsSpellKnown then return done("unknown_requirement", "Spell requirement API is unavailable.") end
    local known = IsSpellKnown(math.abs(q.requiredSpell))
    if q.requiredSpell > 0 and not known then localState,localReason="blocked_profession", "Learn the required spell or specialization." end
    if q.requiredSpell < 0 and known then return done("permanently_locked", "A known spell closes this quest opportunity.") end
  end
  if q.requiredMinRep or q.requiredMaxRep then
    if not c.reputationsReady then return done("unknown_requirement", "Reputation data is not ready.") end
    local function value(id)
      local rep = c.reputations[id]
      return rep and rep.value or (c.belowNeutral[id] and -36000 or 0)
    end
    if q.requiredMinRep and value(q.requiredMinRep[1]) < q.requiredMinRep[2] then localState,localReason="blocked_reputation", "Increase reputation with faction "..q.requiredMinRep[1].."." end
    if q.requiredMaxRep and value(q.requiredMaxRep[1]) >= q.requiredMaxRep[2] then return done("permanently_locked", "Exceeded the source's maximum reputation threshold.") end
  end
  local blocked
  local function dependency(id, allowActive)
    if c.completed[id] or (allowActive and c.active[id]) then return true end
    local record = self.records[id]
    if not record then return false, "unknown_dependency" end
    local state = self:Classify(record, c, visiting)
    if string.find(state, "unknown", 1, true) then return false, "unknown_dependency" end
    if not possible[state] then
      return false, string.find(state, "temporarily", 1, true) and "temporarily_unavailable" or "unreachable_dependency"
    end
    return false, "prerequisite_blocked"
  end
  for _, group in ipairs(self:RequirementGroups(q)) do
    local satisfied, reachable, uncertain, temporary = false, nil, nil, nil
    for _, id in ipairs(group) do
      local ok, state = dependency(id)
      if ok then satisfied = true; break end
      if state == "prerequisite_blocked" then reachable = id
      elseif state == "unknown_dependency" then uncertain = id
      elseif state == "temporarily_unavailable" then temporary = id end
    end
    if not satisfied then
      if reachable then blocked = reachable
      else return done(uncertain and "unknown_dependency" or temporary and "temporarily_unavailable" or "unreachable_dependency", "No verified reachable prerequisite alternative.", uncertain or temporary or group[1]) end
    end
  end
  if q.parentQuest and c.completed[q.parentQuest] and not c.active[q.parentQuest] then
    return done("permanently_locked", "The parent must remain active; it has already been turned in.", q.parentQuest)
  end
  for _, pair in ipairs({{q.parentQuest, true}, {q.enabledBy, true}}) do
    if pair[1] then
      local satisfied, state = dependency(pair[1], pair[2])
      if not satisfied then
        if state ~= "prerequisite_blocked" then return done(state, "Parent or enabling quest is not reachable.", pair[1]) end
        blocked = pair[1]
      end
    end
  end
  if q.unknownAvailability then return done("unknown_availability", "No verified starter or availability information.") end
  if localState then return done(localState, localReason, blocked) end
  if c.level < (q.requiredLevel or 0) then return done("level_locked", "Reach level "..q.requiredLevel..".") end
  if blocked then return done("prerequisite_blocked", "Complete or accept the required prerequisite.", blocked) end
  return done("available", "Available according to current source and character data.")
end

-- Solve compatible outcomes including their dependent quests. Components include
-- dependencies, so overlapping branches are counted once, not independently.
function Eligibility:Project()
  local c, pool, signature = Addon.modules.Character.snapshot, {}, {}
  for id, q in pairs(self.records) do
    if self:InFaction(q) and (self:CompletedOnce(id) or possible[self.states[id]]) then
      pool[id] = true
      table.insert(signature, id .. (self:CompletedOnce(id) and "d" or c.active[id] and "a" or "p"))
    end
  end
  table.sort(signature)
  signature = table.concat(signature, ",")
  if signature == self.projectionSignature then return self.projected end
  self.projectionSignature = signature
  self.projectionIncomplete = false
  local adjacency = {}
  for id in pairs(pool) do adjacency[id] = {} end
  local function edge(a,b)
    if pool[a] and pool[b] then adjacency[a][b]=true; adjacency[b][a]=true end
  end
  for id in pairs(pool) do
    local q = self.records[id]
    for other in pairs(self.conflicts[id] or {}) do edge(id,other) end
    for _, group in ipairs(self:RequirementGroups(q)) do for _, other in ipairs(group) do edge(id,other) end end
    if q.parentQuest then edge(id,q.parentQuest) end
    if q.enabledBy then edge(id,q.enabledBy) end
  end
  local projected, visited = {}, {}
  local ordered = {}; for id in pairs(pool) do table.insert(ordered,id) end; table.sort(ordered)
  for _, root in ipairs(ordered) do
    if not visited[root] then
      local component, todo = {}, {root}
      while #todo > 0 do
        local id = table.remove(todo)
        if not visited[id] then
          visited[id], component[id] = true, true
          for other in pairs(adjacency[id]) do if not visited[other] then table.insert(todo,other) end end
        end
      end
      local best, bestCount, attempts = {}, -1, 0
      local function solve(set)
        attempts = attempts + 1
        if attempts > 4096 then self.projectionIncomplete = true; return end
        local changed = true
        while changed do
          changed = false
          for id in pairs(set) do
            if not self:CompletedOnce(id) and not c.active[id] then
              local q, valid = self.records[id], true
              local function has(d) return c.completed[d] or set[d] end
              for _, group in ipairs(self:RequirementGroups(q)) do
                local any = false
                for _, d in ipairs(group) do if has(d) then any=true; break end end
                if not any then valid=false end
              end
              if q.parentQuest and not has(q.parentQuest) then valid=false end
              if q.enabledBy and not has(q.enabledBy) then valid=false end
              if not valid then set[id]=nil; changed=true end
            end
          end
        end
        local count, a, b = 0
        for id in pairs(set) do
          count = count + 1
          for other in pairs(self.conflicts[id] or {}) do
            if set[other] and not ((self:CompletedOnce(id) or c.active[id]) and (self:CompletedOnce(other) or c.active[other])) then
              if not a or id < a or (id == a and other < b) then a,b=id,other end
            end
          end
        end
        if count <= bestCount then return end
        if not a then best,bestCount=set,count; return end
        for _, remove in ipairs({b,a}) do
          if not self:CompletedOnce(remove) and not c.active[remove] then
            local branch = {}; for id in pairs(set) do if id~=remove then branch[id]=true end end
            solve(branch)
          end
        end
      end
      solve(component)
      -- Even inconsistent source relationships must never erase observed work.
      for id in pairs(component) do
        if self:CompletedOnce(id) or c.active[id] then best[id]=true end
      end
      for id in pairs(best) do projected[id]=true end
    end
  end
  self.projected = projected
  return projected
end
function Eligibility:Rebuild()
  self:ResolveRecords()
  self.results, self.states = {}, {}
  local c = Addon.modules.Character.snapshot
  for id,q in pairs(self.records) do self.states[id] = self:Classify(q,c,{}) end
  local projected = self:Project()
  local summary = {completionistTotal=0, completionistCompleted=0, achievableTotal=0, achievableCompleted=0,
    available=0, blocked=0, locked=0, unknown=0, recurringLifetime=0, recurringAvailable=0, deferred=0, alternatives=0}
  local zones = {}
  for id,q in pairs(self.records) do
    if self:InFaction(q) then
      local state, once = self.states[id], self:CompletedOnce(id)
      local zone = zones[q.canonicalZone]
      if not zone then
        zone = {id=q.canonicalZone, name=q.zoneName, completionistTotal=0, completionistCompleted=0,
          achievableTotal=0, achievableCompleted=0, available=0, actionable=0, blocked=0, locked=0, recurring=0, geographic=q.canonicalZone>0}
        zones[q.canonicalZone]=zone
      end
      for _, counter in ipairs({summary,zone}) do
        counter.completionistTotal=counter.completionistTotal+1
        if once then counter.completionistCompleted=counter.completionistCompleted+1 end
        if projected[id] then
          counter.achievableTotal=counter.achievableTotal+1
          if once then counter.achievableCompleted=counter.achievableCompleted+1 end
        end
      end
      if not q.permanent then
        zone.recurring=zone.recurring+1
        if once then summary.recurringLifetime=summary.recurringLifetime+1 end
        if possible[state] then summary.recurringAvailable=summary.recurringAvailable+1 end
      end
      if string.find(state,"unknown",1,true) then summary.unknown=summary.unknown+1 end
      if Addon.charDB.deferred[id] and not once then summary.deferred=summary.deferred+1 end
      if not once then
        if state=="available" or state=="active" or state=="ready_to_turn_in" then
          summary.available=summary.available+1; zone.available=zone.available+1; zone.actionable=zone.actionable+1
        elseif string.find(state,"blocked",1,true) or state=="level_locked" then
          summary.blocked=summary.blocked+1; zone.blocked=zone.blocked+1
        elseif state=="permanently_locked" or state=="unreachable_dependency" then summary.locked=summary.locked+1; zone.locked=zone.locked+1 end
        if possible[state] and not projected[id] then summary.alternatives=summary.alternatives+1 end
      end
    end
  end
  summary.provisional = summary.unknown>0 or self.projectionIncomplete
  summary.phase = Addon.db.phaseOverride or Addon.Manifest.phase.number
  local previous = self.summary
  summary.changed = previous.achievableTotal and previous.achievableTotal~=summary.achievableTotal
  self.summary,self.zones=summary,zones
end
function Eligibility:GetState(id) return self.states[id] end
function Eligibility:GetResult(id) return self.results[id] or {state="unknown",reason="Quest data is not ready."} end
function Eligibility:IsRoutable(id, includeBlocked)
  local state=self.states[id]
  return state=="available" or state=="active" or state=="ready_to_turn_in" or (includeBlocked and possible[state])
end
function Eligibility:IsRecommendedChoice(id) return self.projected and self.projected[id] == true end
