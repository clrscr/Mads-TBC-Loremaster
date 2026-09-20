local Addon=MadsTBC
local Planning={}
Addon:RegisterModule("Planning",Planning)

function Planning:Initialize() self.forecast,self.risks={},{} end
local function name(id)
  local q=Addon:GetQuest(id)
  return q and q.name or ("Quest "..tostring(id))
end
local trainedRanks={"Apprentice","Journeyman","Expert","Artisan","Master"}
local function rankName(professionID,tier)
  local professions=Addon:Import("QuestieProfessions")
  local function label(method,id,fallback)
    if professions and type(professions[method])=="function" then
      local ok,value=pcall(professions[method],professions,id)
      if ok and type(value)=="string" and value~="" then return value end
    end
    return fallback
  end
  return label("GetRankName",tier,trainedRanks[tier] or ("rank "..tier)).." "..label("GetProfessionName",professionID,"profession "..professionID)
end
local function pointIn(sources,area)
  for _,source in ipairs(sources or {}) do
    for _,p in ipairs(source.points or (source.point and {source.point}) or {}) do
      if p.areaId==area then return true end
    end
  end
  return false
end
function Planning:InZone(q,area)
  if not area then return false end
  return q.canonicalZone==area or pointIn(q.starters,area) or pointIn(q.finishers,area) or pointIn(q.objectives,area)
end

-- Forecast every unfinished compatible opportunity, including skipped and
-- excluded work. Preferences must never hide an impending loss.
function Planning:Rebuild()
  local e,c=Addon.modules.Eligibility,Addon.modules.Character.snapshot
  self.forecast,self.risks={},{}
  for id,q in pairs(e.records or {}) do
    local state=e:GetState(id) or "unknown"
    if e:InFaction(q) and not e:CompletedOnce(id) and state~="ineligible_race" and state~="ineligible_class"
      and state~="permanently_locked" and state~="unreachable_dependency" then
      local reasons,priority={},3
      local function add(message,urgent)
        reasons[#reasons+1]=message
        if urgent then priority=1 end
      end
      -- Level/rank acquisition gates no longer threaten a quest already held.
      if not c.active[id] then
        if q.maximumLevel then
          add("Pick up by level "..q.maximumLevel.."; unavailable at level "..(q.maximumLevel+1)..".",c.level>=q.maximumLevel-1)
        end
        for _,field in ipairs({"breadcrumbFor","nextQuest"}) do
          if q[field] and (field~="nextQuest" or q[field]~=q.breadcrumbFor) then
            add("Complete this before accepting "..name(q[field])..". That quest supersedes this opportunity.",c.active[q[field]]~=nil)
          end
        end
        if q.requiredMaxRep then
          local rep=c.reputations[q.requiredMaxRep[1]]
          add("Complete before reputation with faction "..q.requiredMaxRep[1].." reaches "..q.requiredMaxRep[2]..
            (rep and (" (current "..rep.value..").") or " (current value unknown)."),false)
        end
        for _,rank in ipairs(q.requiredRanks or {}) do
          if rank[2]<0 then add("Complete before training "..rankName(rank[1],-rank[2])..".",false) end
        end
        if q.requiredSpell and q.requiredSpell<0 then add("Complete before learning spell "..(-q.requiredSpell)..".",false) end
      end
      if q.availableUntilCompleted then add("Complete before turning in "..name(q.availableUntilCompleted)..".",c.active[q.availableUntilCompleted]~=nil) end
      if q.parentQuest then add("Finish this child quest before turning in its parent, "..name(q.parentQuest)..".",c.active[q.parentQuest]~=nil) end
      for other in pairs(e.conflicts[id] or {}) do
        if not e:CompletedOnce(other) then add("Alternative outcome: accepting or completing "..name(other).." may close this quest.",c.active[other]~=nil) end
      end
      if q.eventOnly then add("Event opportunity: finish while available. An end date is not established by the source.",state=="available" or c.active[id]~=nil) end
      if #reasons>0 then
        if state=="temporarily_unavailable" then priority=1 end
        table.sort(reasons)
        local row={id=id,name=q.name,priority=priority,reasons=reasons}
        self.forecast[#self.forecast+1]=row; self.risks[id]=row
      end
    end
  end
  table.sort(self.forecast,function(a,b)
    if a.priority~=b.priority then return a.priority<b.priority end
    if a.name~=b.name then return a.name<b.name end
    return a.id<b.id
  end)
end

-- Determine downstream losses with the same all-of / any-of semantics as
-- eligibility. A surviving alternative is not counted as a lost descendant.
function Planning:Consequences(id)
  local e,c=Addon.modules.Eligibility,Addon.modules.Character.snapshot
  local lost={[id]=true}; local changed=true
  while changed do
    changed=false
    for other,q in pairs(e.records or {}) do
      if not lost[other] and not e:CompletedOnce(other) and not c.active[other] and e:InFaction(q)
        and e:IsRoutable(other,true) then
        local blocked=lost[q.parentQuest] or lost[q.enabledBy]
        for _,group in ipairs(e:RequirementGroups(q)) do
          local allLost=#group>0
          for _,dependency in ipairs(group) do
            if not lost[dependency] or c.completed[dependency] then allLost=false; break end
          end
          if allLost then blocked=true end
        end
        if blocked then lost[other]=true; changed=true end
      end
    end
  end
  lost[id]=nil
  local rows={}
  for other in pairs(lost) do rows[#rows+1]={id=other,name=name(other)} end
  table.sort(rows,function(a,b) return a.id<b.id end)
  return rows
end

function Planning:Checklist(area)
  local e,s=Addon.modules.Eligibility,Addon.modules.Selection
  local rows,counts={}, {turn_in=0,pickup=0,finish=0,chain=0,later=0,preferences=0,unknown=0,locked=0}
  local order={turn_in=1,pickup=2,finish=3,chain=4,later=5,preferences=6,unknown=7,locked=8}
  for id,q in pairs(e.records or {}) do
    local state=e:GetState(id) or "unknown"
    if self:InZone(q,area) and e:InFaction(q) and not e:CompletedOnce(id)
      and state~="ineligible_race" and state~="ineligible_class" then
      local check=s:Check(id)
      local group,reason
      if not check.allowed or not s:Matches(q) then group="preferences"; reason=not check.allowed and check.reason or "Outside selected categories."
      elseif state:find("unknown",1,true) then group="unknown"
      elseif state=="permanently_locked" or state=="unreachable_dependency" then group="locked"
      elseif state=="ready_to_turn_in" and pointIn(q.finishers,area) then group="turn_in"
      elseif state=="available" and pointIn(q.starters,area) then group="pickup"
      elseif state=="active" and (pointIn(q.objectives,area) or q.canonicalZone==area) then group="finish"
      elseif state=="prerequisite_blocked" then group="chain"
      else group="later" end
      counts[group]=counts[group]+1
      rows[#rows+1]={id=id,name=q.name,group=group,reason=reason or e:GetResult(id).reason,risk=self.risks[id]}
    end
  end
  table.sort(rows,function(a,b)
    if order[a.group]~=order[b.group] then return order[a.group]<order[b.group] end
    if (a.risk~=nil)~=(b.risk~=nil) then return a.risk~=nil end
    if a.name~=b.name then return a.name<b.name end
    return a.id<b.id
  end)
  return rows,counts
end
