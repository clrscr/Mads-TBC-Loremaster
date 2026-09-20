local Addon=MadsTBC
local Selection={}
Addon:RegisterModule("Selection",Selection)
Selection.categories={
  {"general","General questing"},{"dungeon","Dungeon (includes Heroic)"},{"raid","Raid"},
  {"profession","Profession / skills"},{"class","Class"},{"pvp","PvP"},
  {"reputation","Reputation"},{"recurring","Recurring"},{"event","Seasonal / event"},
  {"group","Group / elite"},{"legendary","Legendary"},{"unknown","Unclassified"},
}
local labels={}
for _,category in ipairs(Selection.categories) do labels[category[1]]=category[2] end
function Selection:Normalize(value)
  local rules={}
  for key,state in pairs(type(value)=="table" and value or {}) do
    if labels[key] and (state=="include" or state=="exclude") then rules[key]=state end
  end
  return rules
end
function Selection:Initialize()
  self.categoryCache=setmetatable({},{__mode="k"})
  self.summary,self.zones,self.bridges,self.checks={}, {}, {}, {}
end
function Selection:Categories(q)
  local cached=self.categoryCache[q]
  if cached then return cached end
  local kinds={}; for _,kind in ipairs(q.kinds or {}) do kinds[kind]=true end
  local result={}
  result.dungeon=q.category=="dungeon" or kinds.dungeon or kinds.heroic or false
  result.raid=q.category=="raid" or kinds.raid or false
  result.profession=q.category=="profession" or kinds.profession_gated or q.requiredSkill~=nil or q.requiredRanks~=nil or q.requiredSpecialization~=nil
  result.class=q.category=="hunter" or kinds.hunter or (q.requiredClasses~=nil and q.requiredClasses~=0 and q.requiredClasses~=1503)
  result.pvp=q.category=="pvp" or kinds.pvp or false
  result.reputation=q.category=="reputation" or kinds.reputation or kinds.reputation_gated or q.requiredMinRep~=nil or q.requiredMaxRep~=nil
  result.recurring=q.permanent==false
  result.event=q.eventOnly==true or kinds.seasonal_or_event or kinds.world_event or false
  result.group=result.dungeon or result.raid or kinds.group_content or kinds.elite or false
  result.legendary=q.category=="legendary" or kinds.legendary or false
  result.unknown=q.category=="unknown"
  result.general=not (result.dungeon or result.raid or result.profession or result.class or result.pvp or result.reputation or result.legendary or result.unknown)
  self.categoryCache[q]=result
  return result
end
function Selection:Excluded(q)
  local categories=self:Categories(q)
  for _,category in ipairs(self.categories) do
    if Addon.charDB.categoryPreferences[category[1]]=="exclude" and categories[category[1]] then return category[2] end
  end
end
function Selection:Matches(q)
  if self:Excluded(q) then return false end
  local categories,hasIncludes,match=self:Categories(q),false,false
  for key,state in pairs(Addon.charDB.categoryPreferences) do
    if state=="include" then hasIncludes=true; if categories[key] then match=true end end
  end
  return not hasIncludes or match
end
function Selection:Description()
  local included,excluded={},{}
  for _,category in ipairs(self.categories) do
    local state=Addon.charDB.categoryPreferences[category[1]]
    if state=="include" then table.insert(included,category[2]) end
    if state=="exclude" then table.insert(excluded,category[2]) end
  end
  return (#included>0 and ("Include: "..table.concat(included,", ")) or "All categories")
    ..(#excluded>0 and ("; Exclude: "..table.concat(excluded,", ")) or "")
end
function Selection:Changed(reason)
  -- Preferences only alter selection. Never rescan the client or rewrite the
  -- global compatible projection merely because a filter or skip changed.
  Addon.modules.Router:Refresh()
  Addon:Emit("STATE_UPDATED",reason)
end
function Selection:SetCategory(key,state)
  if not labels[key] or (state~="any" and state~="include" and state~="exclude") then return end
  Addon.charDB.categoryPreferences[key]=state~="any" and state or nil
  self:Changed("categories")
end
function Selection:ResetCategories()
  Addon.charDB.categoryPreferences={}
  self:Changed("categories")
end
local function counter()
  return {completionistTotal=0,completionistCompleted=0,achievableTotal=0,achievableCompleted=0,visible=0}
end
function Selection:MarkBridge(q,goal)
  if self.bridges[q.id] then return end
  self.bridges[q.id]=goal
  local zone=self.zones[q.canonicalZone]
  if not zone then zone=counter(); zone.id,zone.name=q.canonicalZone,q.zoneName; self.zones[q.canonicalZone]=zone end
  zone.visible=zone.visible+1
  zone.bridges=(zone.bridges or 0)+1
end
function Selection:Rebuild()
  self.checks,self.bridges,self.focusedGoal={}, {}, nil
  self.summary,self.zones=counter(),{}
  self.skipped=0
  local e=Addon.modules.Eligibility
  self.summary.provisional=e.summary.provisional
  for id,q in pairs(e.records or {}) do
    if e:InFaction(q) then
      local once=e:CompletedOnce(id)
      if Addon.charDB.deferred[id] and not once then self.skipped=self.skipped+1 end
      if self:Matches(q) then
        local zone=self.zones[q.canonicalZone]
        if not zone then zone=counter(); zone.id,zone.name=q.canonicalZone,q.zoneName; self.zones[q.canonicalZone]=zone end
        for _,counts in ipairs({self.summary,zone}) do
          counts.visible=counts.visible+1
          counts.completionistTotal=counts.completionistTotal+1
          if once then counts.completionistCompleted=counts.completionistCompleted+1 end
          if e:IsRecommendedChoice(id) then
            counts.achievableTotal=counts.achievableTotal+1
            if once then counts.achievableCompleted=counts.achievableCompleted+1 end
          end
        end
      end
    end
  end
end
-- accessOnly asks whether a parent/enabler can be accepted, not completed.
-- Keeping these distinct avoids treating a legitimate parent/child association
-- as a cycle, or requiring the parent's other children just to accept it.
function Selection:Check(id,accessOnly,visiting)
  local key=id..(accessOnly and ":accept" or ":complete")
  if self.checks[key] then return self.checks[key] end
  local e,c=Addon.modules.Eligibility,Addon.modules.Character.snapshot
  local q=e.records and e.records[id]
  local result={allowed=true,dependencies={},children={}}
  if not q then return result end
  local excluded=self:Excluded(q)
  if Addon.charDB.deferred[id] or excluded then
    result.allowed=false; result.blocker=id
    result.reason=Addon.charDB.deferred[id] and ("Skipped quest: "..q.name..". Restore it to resume this work.")
      or ("Excluded category: "..excluded.." ("..q.name.."). Change Categories to include this work.")
    self.checks[key]=result; return result
  end
  visiting=visiting or {}
  if visiting[key] then return result end -- eligibility separately diagnoses source cycles
  visiting[key]=true
  local function blocked(by)
    visiting[key]=nil
    result.allowed,result.reason,result.blocker=false,by.reason,by.blocker
    self.checks[key]=result
    return result
  end
  if not c.active[id] then
    for _,group in ipairs(e:RequirementGroups(q)) do
      local satisfied,candidates=false,{}
      for _,dependency in ipairs(group) do
        if c.completed[dependency] then satisfied=true end
        if e:IsRoutable(dependency,true) then table.insert(candidates,dependency) end
      end
      if not satisfied then
        table.sort(candidates,function(a,b)
          local ap,bp=e:IsRecommendedChoice(a),e:IsRecommendedChoice(b)
          if ap~=bp then return ap end
          local aa,ba=c.active[a]~=nil,c.active[b]~=nil
          if aa~=ba then return aa end
          return a<b
        end)
        local chosen,failure
        for _,dependency in ipairs(candidates) do
          local check=self:Check(dependency,false,visiting)
          if check.allowed then chosen=dependency; break end
          failure=failure or check
        end
        if chosen then table.insert(result.dependencies,{id=chosen})
        elseif failure then return blocked(failure) end
      end
    end
    for _,dependency in ipairs({q.parentQuest or 0,q.enabledBy or 0}) do
      if dependency>0 and not c.completed[dependency] and not c.active[dependency] then
        local check=self:Check(dependency,true,visiting)
        if not check.allowed then return blocked(check) end
        table.insert(result.dependencies,{id=dependency,accessOnly=true})
      end
    end
  end
  if not accessOnly and not (c.active[id] and c.active[id].complete) then
    local pending,allowed,failures,failure={}, {}, {}, nil
    for _,child in ipairs(e.children[id] or {}) do
      if not e:CompletedOnce(child) and e:IsRoutable(child,true) then
        table.insert(pending,child)
        local check=self:Check(child,false,visiting)
        if check.allowed then table.insert(allowed,child)
        else failures[child]=check; failure=failure or check end
      end
    end
    table.sort(allowed,function(a,b)
      local aa,ba=c.active[a]~=nil,c.active[b]~=nil
      if aa~=ba then return aa end
      local ap,bp=e:IsRecommendedChoice(a),e:IsRecommendedChoice(b)
      if ap~=bp then return ap end
      return a<b
    end)
    local chosen={}
    local function conflicts(a,b) return e.conflicts[a] and e.conflicts[a][b] end
    -- Each child needs either its own work or a directly exclusive alternative.
    -- Do not turn a whole connected conflict component into an any-of group:
    -- two children can share an alternative without being alternatives themselves.
    local function choose()
      local needed
      for _,child in ipairs(pending) do
        local covered=false
        for _,pick in ipairs(chosen) do
          if child==pick or conflicts(child,pick) then covered=true; break end
        end
        if not covered then needed=child; break end
      end
      if not needed then return true end
      local descendantFailure
      for _,child in ipairs(allowed) do
        if child==needed or conflicts(child,needed) then
          local compatible=true
          for _,pick in ipairs(chosen) do
            if conflicts(child,pick) then compatible=false; break end
          end
          if compatible then
            table.insert(chosen,child)
            local solved,reason=choose()
            if solved then return true end
            descendantFailure=descendantFailure or reason
            table.remove(chosen)
          end
        end
      end
      return false,descendantFailure or failures[needed] or failure
    end
    local allowedChildren,childFailure=choose()
    if not allowedChildren then return blocked(childFailure) end
    result.children=chosen
  end
  visiting[key]=nil
  self.checks[key]=result
  return result
end
function Selection:Visible(q)
  return self:Matches(q) or self.bridges[q.id]~=nil or self.focusedGoal==q.id
end
function Selection:BridgeText(id)
  local goal=self.bridges[id]
  local q=goal and Addon:GetQuest(goal)
  if q then return "Required prerequisite for "..q.name end
end
