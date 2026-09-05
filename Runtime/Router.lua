local Addon = MadsTBC
local Router = {}
Addon:RegisterModule("Router", Router)
local labels = {journey="Adaptive Journey", continue="Adaptive Journey", catchup="Catch Up",
  back_on_track="Get Back on Track", zone="Zone Focus", cleanup="Zone Cleanup", recurring="Recurring Activity", quest="Quest Goal"}
function Router:Initialize()
  self.plan, self.index = {}, 1
  self.currentKey = type(Addon.charDB.currentActionKey)=="string" and Addon.charDB.currentActionKey or nil
end
local function level(q) return math.max(q.requiredLevel or 1, q.questLevel or 1) end
local function urgency(q)
  local risk=Addon.modules.Planning.risks[q.id]
  if risk and risk.priority==1 then return 2 end
  return (q.maximumLevel or q.breadcrumbFor or q.availableUntilCompleted) and 1 or 0
end
function Router:Build(mode, zoneID, goalID)
  local e, c = Addon.modules.Eligibility, Addon.modules.Character.snapshot
  local selection=Addon.modules.Selection
  local selected,needed,expanded={}, {}, {}
  self.preferenceReason=nil
  local function add(id,force,goal,accessOnly)
    local q=e.records[id]
    if not q or not e:InFaction(q) then return end
    local check=selection:Check(id,accessOnly)
    if not check.allowed then self.preferenceReason=self.preferenceReason or check.reason; return end
    selected[id]=true
    if force then needed[id]=true end
    if not selection:Matches(q) and id~=goal then selection:MarkBridge(q,goal) end
    local key=id..(accessOnly and ":accept" or ":complete")
    if expanded[key] then return end
    expanded[key]=true
    for _,dependency in ipairs(check.dependencies) do add(dependency.id,true,goal,dependency.accessOnly) end
    for _,child in ipairs(check.children) do add(child,true,goal) end
  end
  if mode=="quest" then
    if goalID then selection.focusedGoal=goalID; add(goalID,true,goalID) end
  else
    local roots={}
    for id,q in pairs(e.records) do
      local inScope=(mode~="zone" or q.canonicalZone==zoneID)
        and (mode~="cleanup" or Addon.modules.Planning:InZone(q,zoneID))
        and (mode~="recurring" or (not q.permanent and (not zoneID or q.canonicalZone==zoneID)))
        and (mode~="catchup" or level(q)<c.level)
      if inScope and selection:Matches(q) and e:InFaction(q)
        and (mode=="recurring" or not e:CompletedOnce(id) or c.active[id])
        and (e:IsRecommendedChoice(id) or c.active[id]) then table.insert(roots,id) end
    end
    table.sort(roots)
    for _,id in ipairs(roots) do add(id,false,id) end
  end
  local actions = {}
  local function append(q, kind, objective, text)
    table.insert(actions, {questID=q.id, type=kind, objectiveIndex=objective,
      key=kind..":"..q.id..":"..(objective or 0), text=text, urgency=urgency(q)})
  end
  for id in pairs(selected) do
    local q,state=e.records[id],e:GetState(id)
    if not Addon.charDB.deferred[id] then
      if state=="ready_to_turn_in" then append(q,"turn_in")
      elseif state=="active" then
        local childrenPending=false
        for _, child in ipairs(e.children[id] or {}) do
          if not e:CompletedOnce(child) and e:IsRoutable(child,true) then childrenPending=true end
        end
        if not childrenPending then
          local live=c.active[id]
          local count=0
          for index,objective in ipairs(live.objectives or {}) do
            if not objective.finished then append(q,"objective",index,objective.text); count=count+1 end
          end
          if count==0 then append(q,"objective",nil,live.failed and "Quest failed. Inspect your quest log before retrying." or nil) end
        end
      elseif state=="available" and (mode=="recurring" or needed[id] or not e:CompletedOnce(id)) then
        if c.logUsed < math.max(1,c.logMaximum-2) then append(q,"accept") end
      end
    end
  end
  local filtered=actions
  -- Cache endpoint distances once per build, never call map APIs in the sort.
  local position=Addon.modules.Navigation:PlayerPosition()
  local zoneScores={}
  for _, action in ipairs(filtered) do
    local point,_,distance=Addon.modules.Navigation:_PointForAction(action,position)
    local q=e.records[action.questID]
    action.areaID=point and point.areaId or q.canonicalZone
    action.distance=distance or math.huge
    action.travel=Addon.modules.Travel:Route(point)
    action.travelCost=action.travel and action.travel.cost or math.huge
    local score=math.abs(level(q)-c.level)
    zoneScores[action.areaID]=math.min(zoneScores[action.areaID] or math.huge,score)
  end
  table.sort(filtered,function(a,b)
    if a.urgency~=b.urgency then return a.urgency>b.urgency end
    local aq,bq=e.records[a.questID],e.records[b.questID]
    -- Retain a useful action unless a known missable opportunity takes priority.
    local ap,bp=a.key==self.currentKey,b.key==self.currentKey
    if ap~=bp then return ap end
    local al,bl=a.areaID==c.currentAreaID,b.areaID==c.currentAreaID
    if al~=bl then return al end
    local aa,ba=c.active[a.questID]~=nil,c.active[b.questID]~=nil
    if aa~=ba then return aa end
    if a.travelCost~=b.travelCost then return a.travelCost<b.travelCost end
    -- A stable tuple is essential: comparing distance only for same-zone
    -- pairs before a different cross-zone criterion can make sort non-transitive.
    local az,bz=zoneScores[a.areaID],zoneScores[b.areaID]
    if az~=bz then return az<bz end
    if a.areaID~=b.areaID then return a.areaID<b.areaID end
    if a.distance~=b.distance then return a.distance<b.distance end
    local ad,bd=math.abs(level(aq)-c.level),math.abs(level(bq)-c.level)
    if ad~=bd then return ad<bd end
    local ar,br=aq.routeOrder or 1000000,bq.routeOrder or 1000000
    if ar~=br then return ar<br end
    return a.key<b.key
  end)
  return filtered
end
function Router:Refresh()
  if not Addon.modules.Character.snapshot.ready then return end
  Addon.modules.Selection:Rebuild()
  Addon.modules.Planning:Rebuild()
  Addon.modules.Travel:Prepare()
  local intent=Addon.charDB.journey
  self.plan=self:Build(intent.mode,intent.zoneID,intent.questID)
  if Addon.charDB.resumeQuestID then
    for i,action in ipairs(self.plan) do
      if action.questID==Addon.charDB.resumeQuestID then
        self.currentKey=action.key
        table.remove(self.plan,i); table.insert(self.plan,1,action); break
      end
    end
    Addon.charDB.resumeQuestID=nil
  end
  Addon.charDB.firstScanComplete=true
  self.index=1
  local current=self.plan[1]
  self.currentKey=current and current.key
  Addon.charDB.currentActionKey=self.currentKey
  self.explanation="No actionable quest matches this focus. Inspect blocked, skipped, and unknown quests in the dashboard."
  if intent.mode=="quest" and intent.questID then self.explanation=Addon.modules.Eligibility:GetResult(intent.questID).reason end
  if not current and next(Addon.charDB.categoryPreferences) and Addon.modules.Selection.summary.completionistTotal==0 then
    self.explanation="No quests match your category selection. Open Categories to change it or reset categories."
  end
  self.explanation=self.preferenceReason or self.explanation
  local c=Addon.modules.Character.snapshot
  if c.logUsed>=c.logMaximum-2 then self.explanation="Quest-log reserve reached. Finish a logged quest or free a slot; no quest will be abandoned automatically." end
  self:_SetNavigation(current)
end
function Router:_SetNavigation(action)
  local ok,message=pcall(Addon.modules.Navigation.SetForAction,Addon.modules.Navigation,action)
  if not ok and message~=self.lastNavigationError then
    self.lastNavigationError=message
    Addon:Print("Waypoint unavailable; quest tracking continues. "..tostring(message))
  elseif ok then self.lastNavigationError=nil end
end
function Router:Start(mode, zoneID, questID)
  if not labels[mode] then return end
  if mode=="continue" then mode="journey" end
  Addon.charDB.journey={mode=mode,zoneID=zoneID,questID=questID}
  Addon.charDB.routeMode=mode
  self.currentKey=nil
  Addon.charDB.firstScanComplete=true
  self:Refresh()
  Addon:Emit("STATE_UPDATED","route")
end
function Router:GetCurrent()
  local action=self.plan and self.plan[1]
  if not action then return nil end
  return Addon:GetQuest(action.questID),Addon.modules.Eligibility:GetState(action.questID),1,#self.plan,action
end
function Router:DescribeStep(q,state,action)
  action=action or (self.plan and self.plan[1])
  if action and action.text then return action.text end
  if state=="ready_to_turn_in" then return "Turn in "..q.name end
  if state=="active" then return "Complete "..q.name end
  return "Accept "..q.name
end
function Router:SkipCurrent()
  local q=self:GetCurrent()
  if q then self:Skip(q.id) end
end
function Router:Skip(id)
  if not Addon:IsID(id) then return end
  Addon.charDB.deferred[id]=true
  self.currentKey=nil
  Addon.modules.Selection:Changed("skip")
end
function Router:Restore(id)
  if not Addon:IsID(id) then return end
  Addon.charDB.deferred[id]=nil
  Addon.modules.Selection:Changed("restore")
end
function Router:RestoreAll()
  Addon.charDB.deferred={}
  Addon.modules.Selection:Changed("restore_all")
end
-- Preserve callers and saved IDs from the previous private build.
Router.DeferCurrent=Router.SkipCurrent
Router.Defer=Router.Skip
function Router:ModeLabel() return labels[Addon.charDB.journey.mode] or labels.journey end
