local Addon=MadsTBC
local UI={}
Addon:RegisterModule("UI",UI)
-- Centralized addon labels; observed quest titles retain the client's locale.
Addon.Text={title="Mad's TBC Loremaster", journey="Adaptive Journey", completionist="Completionist", achievable="Achievable",
  waiting="Waiting for a reliable character scan…", empty="No quests match these filters.",
  unknown="Unknown availability is not proof of completion or permanent loss.",
  recurring="Each recurring quest counts once toward your journey. Later runs are optional. Older completions may be unknown until observed again."}
local L=Addon.Text
local GOLD={0.84,0.66,0.29}
local function text(parent,size,width)
  local f=parent:CreateFontString(nil,"OVERLAY",size>=16 and "GameFontNormalLarge" or "GameFontHighlight")
  f:SetJustifyH("LEFT"); f:SetJustifyV("TOP"); f:SetWidth(width); f:SetWordWrap(true)
  return f
end
local function button(parent,label,width,x,y,fn)
  local b=CreateFrame("Button",nil,parent,"UIPanelButtonTemplate")
  b:SetSize(width,25); b:SetPoint("TOPLEFT",x,y); b:SetText(label); b:SetScript("OnClick",fn)
  return b
end
local function panel(name,width,height,saved)
  local f=CreateFrame("Frame",name,UIParent,BackdropTemplateMixin and "BackdropTemplate" or nil)
  f:SetSize(width,height); f:SetPoint(saved.point,UIParent,saved.point,saved.x,saved.y)
  f:SetMovable(true); f:EnableMouse(true); f:RegisterForDrag("LeftButton"); f:SetClampedToScreen(true)
  f:SetScript("OnDragStart",f.StartMoving)
  if f.SetBackdrop then
    f:SetBackdrop({bgFile="Interface/Tooltips/UI-Tooltip-Background",edgeFile="Interface/Tooltips/UI-Tooltip-Border",tile=true,tileSize=16,edgeSize=14,insets={left=4,right=4,top=4,bottom=4}})
    f:SetBackdropColor(0.055,0.065,0.085,0.97)
  end
  return f
end
local function savePosition(frame,key)
  frame:StopMovingOrSizing()
  local point,_,_,x,y=frame:GetPoint()
  Addon.db[key]={point=point,x=x,y=y}
end
local function percent(done,total,provisional)
  if total==0 then return "no established total" end
  local value=math.floor(done*100/total)
  return tostring(value).."%"..(provisional and " · provisional" or "")
end
function UI:Initialize()
  self.page,self.zonePage,self.filter="overview",1,"all"
  self:_CreateDashboard(); self:_CreateCategories(); self:_CreateTracker(); self:_CreatePlanner()
  Addon:On("STATE_UPDATED",function() self:Refresh() end)
  if not Addon.charDB.firstScanComplete then self.dashboard:Show() end
end
function UI:_CreateDashboard()
  local f=panel("MadsTBCLoremasterDashboard",860,714,Addon.db.window)
  if UISpecialFrames then table.insert(UISpecialFrames,"MadsTBCLoremasterDashboard") end
  self.dashboard=f; f:Hide(); f:SetFrameStrata("DIALOG")
  f:SetScript("OnDragStop",function(frame) savePosition(frame,"window") end)
  f:SetScript("OnShow",function() self:_RefreshDashboard() end)
  local close=CreateFrame("Button",nil,f,"UIPanelCloseButton"); close:SetPoint("TOPRIGHT",-5,-5)
  local title=text(f,20,780); title:SetPoint("TOPLEFT",22,-18); title:SetText(L.title)
  self.summaryTitle=text(f,18,810); self.summaryTitle:SetPoint("TOPLEFT",22,-56)
  self.summaryBody=text(f,12,810); self.summaryBody:SetPoint("TOPLEFT",22,-83); self.summaryBody:SetHeight(65)
  for i,page in ipairs({"overview","quests","zones","recurring","settings"}) do
    button(f,page:gsub("^%l",string.upper),150,22+(i-1)*160,-218,function() self:SetPage(page) end)
  end
  self.selectionSummary=text(f,12,810); self.selectionSummary:SetPoint("TOPLEFT",22,-151)
  self.categorySummary=text(f,12,810); self.categorySummary:SetPoint("TOPLEFT",22,-176); self.categorySummary:SetHeight(35)
  self.categoryButton=button(f,"Categories",190,620,-18,function() self.categoryPanel:Show() end)
  self.modeButtons={}
  for i,row in ipairs({{"journey","Resume Journey"},{"catchup","Catch Up"},{"back_on_track","Get Back on Track"}}) do
    self.modeButtons[i]=button(f,row[2],180,22+(i-1)*190,-256,function() Addon.modules.Router:Start(row[1]) end)
  end
  self.viewButton=button(f,"",220,607,-256,function()
    Addon:SetProgressView(Addon.db.progressView=="achievable" and "completionist" or "achievable")
  end)
  local search=CreateFrame("EditBox",nil,f,"InputBoxTemplate")
  search:SetSize(270,25); search:SetPoint("TOPLEFT",28,-293); search:SetAutoFocus(false)
  search:SetScript("OnTextChanged",function() self.zonePage=1; self:_RefreshDashboard() end)
  search:SetScript("OnEscapePressed",function(s) s:ClearFocus() end)
  self.search=search
  self.filterButton=button(f,"Filter: all",140,310,-293,function()
    local order={all="available",available="active",active="blocked",blocked="skipped",skipped="completed",completed="inaccessible",inaccessible="unknown",unknown="all"}
    self.filter=order[self.filter]; if self.filter=="skipped" then self.page="quests"; self.selectedZone=nil end; self.zonePage=1; self:_RefreshDashboard()
  end)
  self.zoneFocus=button(f,"Focus zone",140,465,-293,function()
    if self.selectedZone then Addon.modules.Router:Start("zone",self.selectedZone) end
  end)
  self.clearZone=button(f,"All zones",140,620,-293,function() self.selectedZone=nil; self.zonePage=1; self:_RefreshDashboard() end)
  self.zoneRows={}
  for i=1,11 do
    self.zoneRows[i]=button(f,"",392,22,-334-(i-1)*27,function() end)
    self.zoneRows[i]:GetFontString():SetJustifyH("LEFT")
  end
  self.previousZones=button(f,"Previous",90,22,-649,function() self.zonePage=math.max(1,self.zonePage-1); self:_RefreshDashboard() end)
  self.nextZones=button(f,"Next",90,324,-649,function() self.zonePage=self.zonePage+1; self:_RefreshDashboard() end)
  local scroll=CreateFrame("ScrollFrame",nil,f,"UIPanelScrollFrameTemplate")
  scroll:SetPoint("TOPLEFT",435,-334); scroll:SetSize(370,292)
  local child=CreateFrame("Frame",nil,scroll); child:SetSize(368,292); scroll:SetScrollChild(child)
  self.detailScroll,self.detailChild=scroll,child
  self.details=text(child,12,357); self.details:SetPoint("TOPLEFT",0,0)
  self.goalButton=button(f,"Guide this quest",174,435,-649,function()
    if self.selectedQuest then
      local q=Addon:GetQuest(self.selectedQuest)
      if not q or Addon.modules.Selection:Excluded(q) then return end
      if Addon.charDB.deferred[q.id] then Addon.modules.Router:Restore(q.id) end
      Addon.modules.Router:Start("quest",nil,self.selectedQuest)
    end
  end)
  self.deferSelected=button(f,"Skip",174,635,-649,function()
    local id=self.selectedQuest
    if id then
      if Addon.charDB.deferred[id] then Addon.modules.Router:Restore(id)
      else Addon.modules.Router:Skip(id) end
    end
  end)
  self.settingsControls={}
  local function setting(label,y,fn)
    local b=button(f,label,360,26,y,fn); table.insert(self.settingsControls,b); return b
  end
  self.detailButton=setting("",-339,function()
    local order={minimal="route",route="arc",arc="deep",deep="minimal"}; Addon:SetDetailLevel(order[Addon.db.detailLevel])
  end)
  self.phaseButton=setting("",-377,function()
    local phase=Addon.db.phaseOverride
    Addon:SetPhaseOverride(phase and (phase<5 and phase+1 or nil) or 1)
  end)
  self.trackerButton=setting("",-415,function() Addon.db.trackerVisible=not Addon.db.trackerVisible; self:Refresh() end)
  setting("Restore all skipped quests",-453,function() Addon.modules.Router:RestoreAll() end)
  setting("Rescan character",-491,function() Addon:Rescan("manual") end)
  setting("Reset window and tracker positions",-529,function()
    Addon.db.window={point="CENTER",x=0,y=0}; Addon.db.tracker={point="RIGHT",x=-45,y=40}
    self.dashboard:ClearAllPoints(); self.dashboard:SetPoint("CENTER",UIParent,"CENTER",0,0)
    self.tracker:ClearAllPoints(); self.tracker:SetPoint("RIGHT",UIParent,"RIGHT",-45,40)
  end)
  button(f,"Before leaving zone",250,22,-682,function() self:OpenPlanner("checklist",self.selectedZone) end)
  button(f,"Missable forecast",250,300,-682,function() self:OpenPlanner("forecast") end)
  button(f,"Travel planning",250,578,-682,function() self:OpenPlanner("travel") end)
end
function UI:_CreateCategories()
  local f=panel("MadsTBCLoremasterCategories",520,575,{point="CENTER",x=0,y=0})
  f:SetParent(self.dashboard); f:Hide(); f:SetFrameStrata("DIALOG")
  f:ClearAllPoints(); f:SetPoint("CENTER",self.dashboard,"CENTER",0,0)
  self.categoryPanel=f
  if UISpecialFrames then table.insert(UISpecialFrames,"MadsTBCLoremasterCategories") end
  local close=CreateFrame("Button",nil,f,"UIPanelCloseButton"); close:SetPoint("TOPRIGHT",-5,-5)
  local heading=text(f,18,460); heading:SetPoint("TOPLEFT",20,-20); heading:SetText("Journey categories · this character")
  local explanation=text(f,12,475); explanation:SetPoint("TOPLEFT",20,-50)
  explanation:SetText("Include matches any selected category. Exclude always wins. With no Includes, all other categories are allowed.")
  self.categoryControls={}
  for index,category in ipairs(Addon.modules.Selection.categories) do
    local key,label=category[1],category[2]
    local y=-103-(index-1)*32
    local name=text(f,12,210); name:SetPoint("TOPLEFT",20,y-5); name:SetText(label)
    local controls={}; self.categoryControls[key]=controls
    for column,state in ipairs({"any","include","exclude"}) do
      controls[state]=button(f,state,80,230+(column-1)*90,y,function() Addon.modules.Selection:SetCategory(key,state) end)
    end
  end
  local note=text(f,12,475); note:SetPoint("TOPLEFT",20,-490)
  note:SetText("Categories overlap. Group includes dungeons, raids and elite quests. Allowed prerequisites outside Includes are labeled in your journey.")
  self.resetCategories=button(f,"Reset categories",180,20,-533,function() Addon.modules.Selection:ResetCategories() end)
  button(f,"Done",110,390,-533,function() f:Hide() end)
  f:SetScript("OnShow",function() self:_RefreshCategories() end)
end
function UI:_RefreshCategories()
  if not self.categoryPanel or not self.categoryPanel:IsShown() then return end
  for key,controls in pairs(self.categoryControls) do
    local selected=Addon.charDB.categoryPreferences[key] or "any"
    for state,control in pairs(controls) do
      local label=state:gsub("^%l",string.upper)
      control:SetText(state==selected and ("["..label.."]") or label)
      if state==selected then control:Disable() else control:Enable() end
    end
  end
end
function UI:_CreateTracker()
  local f=panel("MadsTBCLoremasterTracker",380,200,Addon.db.tracker)
  self.tracker=f
  f:SetScript("OnDragStop",function(frame) savePosition(frame,"tracker") end)
  self.trackerMode=text(f,12,345); self.trackerMode:SetPoint("TOPLEFT",14,-12)
  self.trackerStep=text(f,14,345); self.trackerStep:SetPoint("TOPLEFT",14,-37)
  self.trackerMeta=text(f,11,345); self.trackerMeta:SetPoint("TOPLEFT",self.trackerStep,"BOTTOMLEFT",0,-8)
  self.trackerOpen=button(f,"Dashboard",105,14,-165,function() self.dashboard:Show() end)
  self.defer=button(f,"Skip",100,130,-165,function() Addon.modules.Router:SkipCurrent() end)
  self.trackerLeave=button(f,"Before leaving",125,240,-165,function() self:OpenPlanner("checklist") end)
end
function UI:SetPage(page)
  self.page,self.zonePage=page,1
  self:_RefreshDashboard()
end
function UI:Toggle() self.dashboard:SetShown(not self.dashboard:IsShown()) end
function UI:_Rows()
  local e=Addon.modules.Eligibility
  local selection=Addon.modules.Selection
  local rows={}
  local search=string.lower(self.search:GetText() or "")
  if self.page=="zones" then
    for _,z in pairs(selection.zones) do if search=="" or string.find(string.lower(z.name),search,1,true) then table.insert(rows,z) end end
    table.sort(rows,function(a,b) if a.name~=b.name then return a.name<b.name end; return a.id<b.id end)
    return rows
  end
  for id,q in pairs(e.records or {}) do
    if e:InFaction(q) and (self.filter=="skipped" or not self.selectedZone or q.canonicalZone==self.selectedZone or selection.bridges[id])
      and (self.filter=="skipped" or self.page~="recurring" or not q.permanent or selection.bridges[id])
      and (self.filter=="skipped" or selection:Visible(q)) then
      local state=e:GetState(id) or "unknown"
      local once=e:CompletedOnce(id)
      local match=self.filter=="all"
        or self.filter=="completed" and once
        or self.filter=="skipped" and Addon.charDB.deferred[id]
        or self.filter=="available" and state=="available" and not once and selection:Check(id).allowed
        or self.filter=="active" and (state=="active" or state=="ready_to_turn_in")
        or self.filter=="blocked" and (string.find(state,"blocked",1,true) or state=="level_locked" or not selection:Check(id).allowed)
        or self.filter=="unknown" and string.find(state,"unknown",1,true)
        or self.filter=="inaccessible" and (string.find(state,"ineligible",1,true) or state=="permanently_locked" or state=="unreachable_dependency" or string.find(state,"temporarily",1,true))
      if match and (search=="" or string.find(string.lower(q.name),search,1,true) or tostring(id)==search) then table.insert(rows,q) end
    end
  end
  table.sort(rows,function(a,b)
    local aa,ba=e:IsRoutable(a.id,false),e:IsRoutable(b.id,false)
    if aa~=ba then return aa end
    if a.zoneName~=b.zoneName then return a.zoneName<b.zoneName end
    if a.name~=b.name then return a.name<b.name end
    return a.id<b.id
  end)
  return rows
end
function UI:_Details()
  local q=self.selectedQuest and Addon:GetQuest(self.selectedQuest)
  if not q then self.details:SetText("Select a quest to inspect its status, requirements, and source instructions.\n\n"..L.unknown); return end
  local e=Addon.modules.Eligibility
  local result=e:GetResult(q.id)
  local lines={q.name.." ("..q.id..")",q.zoneName.." · "..(q.category or "quest"),"",result.reason}
  local selection=Addon.modules.Selection
  local check=selection:Check(q.id)
  if not check.allowed then table.insert(lines,check.reason) end
  local bridge=selection:BridgeText(q.id)
  if bridge then table.insert(lines,bridge) end
  if selection:Excluded(q) then table.insert(lines,"Open Categories to change this exclusion before guiding this quest.") end
  local seen,id={},result.blocker
  while id and not seen[id] do
    seen[id]=true
    local blocker=Addon:GetQuest(id)
    table.insert(lines,"Requires: "..(blocker and blocker.name or ("Uncatalogued quest "..id)))
    id=e:GetResult(id).blocker
  end
  if Addon.charDB.deferred[q.id] then table.insert(lines,"Skipped from guidance until restored. Skipping does not record completion.") end
  if not q.permanent then table.insert(lines,e:CompletedOnce(q.id) and "First completion confirmed. Further runs are optional." or "First completion has not been established.") end
  local live=Addon.modules.Character:IsActive(q.id)
  if live then
    for _,objective in ipairs(live.objectives or {}) do table.insert(lines,(objective.finished and "Done: " or "Next: ")..(objective.text or "Objective data pending")) end
  end
  table.insert(lines,"\nSource instructions:")
  for _,line in ipairs(q.objectiveText or {}) do if type(line)=="string" and line~="" then table.insert(lines,line) end end
  if not q.objectiveText or #q.objectiveText==0 then table.insert(lines,"Special instructions are unavailable. Consult the in-game quest text.") end
  if q.sourceItem then table.insert(lines,"Quest item: "..q.sourceItem) end
  for _,field in ipairs({"starters","finishers"}) do
    for _,source in ipairs(q[field] or {}) do
      table.insert(lines,(field=="starters" and "Starts: " or "Ends: ")..(source.name or (source.kind.." "..source.id)))
    end
  end
  local conflicts={}
  for other in pairs(e.conflicts and e.conflicts[q.id] or {}) do
    local record=Addon:GetQuest(other); if record then table.insert(conflicts,record.name) end
  end
  if #conflicts>0 then table.insert(lines,"\nConflicting outcomes: "..table.concat(conflicts,", ")) end
  table.insert(lines,"\nFacts: pinned Questie TBC source; live availability remains subject to the client.")
  self.details:SetText(table.concat(lines,"\n"))
  self.detailChild:SetHeight(math.max(292,self.details:GetStringHeight()+12))
end
function UI:_RefreshDashboard()
  if not self.dashboard or not self.dashboard:IsShown() then self.dashboardDirty=true; return end
  self.dashboardDirty=false
  local e=Addon.modules.Eligibility
  local s=e.summary or {}
  local selection=Addon.modules.Selection
  local view=Addon.db.progressView
  local done,total=s[view.."Completed"] or 0,s[view.."Total"] or 0
  self.summaryTitle:SetText(Addon.status or (L[view]..": "..done.." / "..total.." ("..percent(done,total,s.provisional)..")"))
  self.summaryBody:SetText(string.format("%s · %d available · %d blocked · %d locked · %d skipped · %d unknown\n%s\nPhase %s (%s). %s",
    Addon.modules.Character.snapshot.faction or "Character scan",s.available or 0,s.blocked or 0,s.locked or 0,selection.skipped or 0,s.unknown or 0,
    view=="completionist" and "All current-faction quests, including other races/classes and conflicting outcomes; recurring quests count once."
      or "Projected compatible outcomes for this character and current conditions; recoverable blockers remain unfinished.",
    tostring(Addon.db.phaseOverride or Addon.Manifest.phase.number),Addon.db.phaseOverride and "manual override" or "packaged profile",
    s.changed and "The achievable total changed with character eligibility." or ""))
  if self.page=="recurring" then self.summaryBody:SetText(L.recurring) end
  local chosen=selection.summary
  local selectedDone,selectedTotal=chosen[view.."Completed"] or 0,chosen[view.."Total"] or 0
  self.selectionSummary:SetText("Selected categories: "..selectedDone.." / "..selectedTotal.." ("..percent(selectedDone,selectedTotal,chosen.provisional)..") · overall totals unchanged")
  self.categorySummary:SetText(self.filter=="skipped" and "Skipped management: all categories and zones. Restore does not change category exclusions." or selection:Description())
  self.viewButton:SetText("Progress: "..L[view])
  local settings=self.page=="settings"
  for _,b in ipairs(self.settingsControls) do b:SetShown(settings) end
  for _,b in ipairs(self.modeButtons) do b:SetShown(not settings) end
  self.search:SetShown(not settings); self.filterButton:SetShown(not settings and self.page~="zones")
  self.zoneFocus:SetShown(not settings and self.selectedZone~=nil); self.clearZone:SetShown(not settings and self.selectedZone~=nil)
  self.detailScroll:SetShown(not settings); self.goalButton:SetShown(not settings); self.deferSelected:SetShown(not settings)
  self.filterButton:SetText("Filter: "..self.filter)
  if settings then
    self.detailButton:SetText("Detail: "..Addon.db.detailLevel)
    self.phaseButton:SetText(Addon.db.phaseOverride and ("Phase override: "..Addon.db.phaseOverride) or ("Packaged phase: "..Addon.Manifest.phase.number))
    self.trackerButton:SetText("Tracker: "..(Addon.db.trackerVisible and "visible" or "hidden"))
  end
  local rows=settings and {} or self:_Rows()
  self.zonePage=math.max(1,math.min(self.zonePage,math.max(1,math.ceil(#rows/11))))
  local start=(self.zonePage-1)*11
  for i,b in ipairs(self.zoneRows) do
    local row=rows[start+i]
    b:SetShown(row~=nil)
    if row then
      if self.page=="zones" then
        b:SetText(row.name.." · "..(row.completionistTotal==0 and "prerequisites only" or (row[view.."Completed"].."/"..row[view.."Total"])))
        b:SetScript("OnClick",function() self.selectedZone=row.id; self.filter="all"; self:SetPage("quests") end)
      else
        local prefix=e:CompletedOnce(row.id) and "Done · " or Addon.charDB.deferred[row.id] and "Skipped · " or selection.bridges[row.id] and "Prerequisite · " or ""
        b:SetText(prefix..row.name)
        b:SetScript("OnClick",function() self.selectedQuest=row.id; self.detailScroll:SetVerticalScroll(0); self:_RefreshDashboard() end)
      end
    end
  end
  self.previousZones:SetShown(not settings and self.zonePage>1)
  self.nextZones:SetShown(not settings and start+11<#rows)
  local selected=self.selectedQuest and Addon:GetQuest(self.selectedQuest)
  self.goalButton:SetText(self.selectedQuest and Addon.charDB.deferred[self.selectedQuest] and "Restore and guide" or "Guide this quest")
  self.deferSelected:SetText(self.selectedQuest and Addon.charDB.deferred[self.selectedQuest] and "Restore" or "Skip")
  if selected and e:IsRoutable(selected.id,true) and not selection:Excluded(selected) then self.goalButton:Enable() else self.goalButton:Disable() end
  if self.selectedQuest then self.deferSelected:Enable() else self.deferSelected:Disable() end
  self:_Details()
end
function UI:_RefreshTracker()
  self.tracker:SetShown(Addon.db.trackerVisible)
  if not Addon.db.trackerVisible then return end
  local q,state,_,total,action=Addon.modules.Router:GetCurrent()
  self.trackerMode:SetText(Addon.modules.Router:ModeLabel()..(next(Addon.charDB.categoryPreferences) and " · categories filtered" or ""))
  if q then
    local live=Addon.modules.Character:IsActive(q.id)
    self.trackerStep:SetText((live and live.title or q.name).."\n"..Addon.modules.Router:DescribeStep(q,state,action))
    local lines={Addon.modules.Navigation:Description()}
    local bridge=Addon.modules.Selection:BridgeText(q.id)
    if bridge then table.insert(lines,1,bridge) end
    local travel=Addon.modules.Navigation:TravelHint()
    if travel then table.insert(lines,travel) end
    if action.areaID~=Addon.modules.Character.snapshot.currentAreaID then
      table.insert(lines,"Heading out of this zone? Review Before leaving for unfinished local work.")
    end
    if not q.permanent then table.insert(lines,"Recurring quest · first-completion journey") end
    if q.category=="dungeon" or q.category=="raid" or q.category=="pvp" or q.category=="elite" then table.insert(lines,"Requires "..q.category.." participation. Skip if you are not ready.") end
    local lore=Addon:GetLore(q.canonicalZone,Addon.db.detailLevel)
    if lore then table.insert(lines,lore) end
    self.trackerMeta:SetText(table.concat(lines,"\n")); self.defer:Show()
  else
    self.trackerStep:SetText(Addon.status or "No actionable step in this focus")
    self.trackerMeta:SetText(Addon.modules.Router.explanation or L.waiting); self.defer:Hide()
  end
  local height=math.max(180,85+self.trackerStep:GetStringHeight()+self.trackerMeta:GetStringHeight())
  self.tracker:SetHeight(height)
  self.trackerOpen:ClearAllPoints(); self.trackerOpen:SetPoint("BOTTOMLEFT",14,12)
  self.defer:ClearAllPoints(); self.defer:SetPoint("BOTTOMLEFT",130,12)
  self.trackerLeave:ClearAllPoints(); self.trackerLeave:SetPoint("BOTTOMLEFT",240,12)
end
function UI:Refresh() self:_RefreshDashboard(); self:_RefreshCategories(); self:_RefreshTracker(); self:_RefreshPlanner() end

local checklistLabels={turn_in="Turn in locally",pickup="Pick up locally",finish="Finish objectives",chain="Unfinished chain",
  later="Return later / travel",preferences="Skipped / filtered",unknown="Needs verification",locked="Inaccessible"}
function UI:_CreatePlanner()
  local f=panel("MadsTBCLoremasterPlanner",820,660,{point="CENTER",x=0,y=0})
  self.planner=f; f:Hide(); f:SetFrameStrata("DIALOG")
  if UISpecialFrames then table.insert(UISpecialFrames,"MadsTBCLoremasterPlanner") end
  f:SetScript("OnDragStop",f.StopMovingOrSizing)
  local close=CreateFrame("Button",nil,f,"UIPanelCloseButton"); close:SetPoint("TOPRIGHT",-5,-5)
  self.plannerTitle=text(f,18,760); self.plannerTitle:SetPoint("TOPLEFT",20,-20)
  for i,entry in ipairs({{"checklist","Before leaving"},{"forecast","Missable forecast"},{"travel","Travel planning"}}) do
    button(f,entry[2],245,20+(i-1)*265,-55,function() self:OpenPlanner(entry[1],self.plannerArea) end)
  end
  self.plannerSummary=text(f,12,775); self.plannerSummary:SetPoint("TOPLEFT",20,-93); self.plannerSummary:SetHeight(70)
  self.plannerSearch=CreateFrame("EditBox",nil,f,"InputBoxTemplate")
  self.plannerSearch:SetSize(350,25); self.plannerSearch:SetPoint("TOPLEFT",26,-175); self.plannerSearch:SetAutoFocus(false)
  self.plannerSearch:SetScript("OnTextChanged",function() self.plannerPage=1; self:_RefreshPlanner() end)
  self.plannerSearch:SetScript("OnEscapePressed",function(s) s:ClearFocus() end)
  self.plannerHere=button(f,"Use current zone",180,410,-175,function()
    self.plannerArea=Addon.modules.Character.snapshot.currentAreaID; self.plannerPage=1; self.plannerQuest=nil; self:_RefreshPlanner()
  end)
  self.plannerCleanup=button(f,"Guide zone cleanup",195,605,-175,function()
    if self.plannerArea then Addon.modules.Router:Start("cleanup",self.plannerArea) end
  end)
  self.plannerRows={}
  for i=1,12 do self.plannerRows[i]=button(f,"",375,20,-215-(i-1)*27,function() end) end
  self.plannerPrevious=button(f,"Previous",100,20,-550,function() self.plannerPage=math.max(1,self.plannerPage-1); self:_RefreshPlanner() end)
  self.plannerNext=button(f,"Next",100,295,-550,function() self.plannerPage=self.plannerPage+1; self:_RefreshPlanner() end)
  local scroll=CreateFrame("ScrollFrame",nil,f,"UIPanelScrollFrameTemplate")
  scroll:SetPoint("TOPLEFT",415,-215); scroll:SetSize(365,355)
  local child=CreateFrame("Frame",nil,scroll); child:SetSize(360,355); scroll:SetScrollChild(child)
  self.plannerScroll,self.plannerChild=scroll,child
  self.plannerDetails=text(child,12,345); self.plannerDetails:SetPoint("TOPLEFT",0,0)
  self.plannerGuide=button(f,"Guide selected quest",235,20,-605,function()
    local q=self.plannerQuest and Addon:GetQuest(self.plannerQuest)
    if q and not Addon.modules.Selection:Excluded(q) and not Addon.charDB.deferred[q.id] then Addon.modules.Router:Start("quest",nil,q.id) end
  end)
  self.plannerInspect=button(f,"Inspect in dashboard",235,280,-605,function()
    if self.plannerQuest then self.selectedQuest=self.plannerQuest; self:SetPage("quests"); self.planner:Hide(); self.dashboard:Show() end
  end)
  self.transportKind="boat"
  self.transportType=button(f,"Connection: boat/zeppelin",375,20,-215,function()
    self.transportKind=({boat="portal",portal="road",road="boat"})[self.transportKind]; self:_RefreshPlanner()
  end)
  self.transportDeparture=button(f,"Record departure here",375,20,-253,function()
    local _,message=Addon.modules.Travel:RecordDeparture(self.transportKind); self.transportMessage=message; self:_RefreshPlanner()
  end)
  self.transportArrival=button(f,"Record arrival here",375,20,-291,function()
    local ok,message=Addon.modules.Travel:RecordArrival(); self.transportMessage=message
    if ok then Addon.modules.Router:Refresh(); self:Refresh() else self:_RefreshPlanner() end
  end)
  self.transportCancel=button(f,"Cancel recorded departure",375,20,-329,function()
    Addon.charDB.travel.pending=nil; self.transportMessage=nil; self:_RefreshPlanner()
  end)
  self.transportHelp=text(f,12,375); self.transportHelp:SetPoint("TOPLEFT",20,-374); self.transportHelp:SetHeight(170)
  button(f,"Refresh",235,545,-605,function() Addon:Rescan("planner") end)
end
function UI:OpenPlanner(mode,area)
  self.plannerMode,self.plannerArea=mode,area or Addon.modules.Character.snapshot.currentAreaID
  self.plannerPage,self.plannerQuest=1,nil
  self.plannerSearch:SetText(""); self.planner:Show(); self:_RefreshPlanner()
end
function UI:_RefreshPlanner()
  if not self.planner or not self.planner:IsShown() then return end
  local p,e,s=Addon.modules.Planning,Addon.modules.Eligibility,Addon.modules.Selection
  local mode=self.plannerMode or "checklist"
  local travel=mode=="travel"
  local zone=e.zones[self.plannerArea]
  self.plannerTitle:SetText(mode=="checklist" and ("Before leaving: "..(zone and zone.name or "current zone unknown"))
    or mode=="forecast" and "Missable quest forecast" or "Character travel planning")
  self.plannerHere:SetShown(mode=="checklist"); self.plannerCleanup:SetShown(mode=="checklist")
  if self.plannerArea then self.plannerCleanup:Enable() else self.plannerCleanup:Disable() end
  self.plannerSearch:SetShown(not travel)
  self.plannerGuide:SetShown(not travel); self.plannerInspect:SetShown(not travel)
  for _,control in ipairs({self.transportType,self.transportDeparture,self.transportArrival,self.transportCancel,self.transportHelp}) do control:SetShown(travel) end
  self.transportType:SetText("Connection: "..(self.transportKind=="boat" and "boat/zeppelin" or self.transportKind))
  local pending=Addon.charDB.travel.pending
  if pending then self.transportArrival:Enable(); self.transportCancel:Enable() else self.transportArrival:Disable(); self.transportCancel:Disable() end
  self.transportHelp:SetText((self.transportMessage or "Choose a connection type and record its departure. Travel through it, then record arrival. Save permanent public connections you can reuse.")..
    (pending and ("\n\nPending "..pending.kind.." departure: "..pending.name..". Saved across reloads.") or "")..
    "\n\nOnly the traveled direction is recorded. Temporary player portals should not be saved.")
  local rows,counts={}
  if mode=="checklist" then
    rows,counts=p:Checklist(self.plannerArea)
    self.plannerSummary:SetText(string.format("%d local turn-ins · %d pickups · %d objectives · %d unfinished chains\n%d later/travel · %d skipped/filtered · %d unknown · %d inaccessible\nCleanup respects Categories and Skip. Prerequisites may take you outside this zone.",
      counts.turn_in,counts.pickup,counts.finish,counts.chain,counts.later,counts.preferences,counts.unknown,counts.locked))
  elseif mode=="forecast" then
    rows=p.forecast
    self.plannerSummary:SetText(#rows.." known opportunities with cutoff or choice conditions. Urgent items appear first.\nIncludes skipped quests and all categories. Unknown conditions are not confirmed losses.\nSelect a quest to see its cutoff, preservation advice, and dependent quests.")
  else
    self.plannerSummary:SetText("Travel memory belongs to this character and survives reloads.\nFlight routes use connections observed in your flight map and endpoints located during visits.\nRefresh after travel to reconsider the route from your current position.")
  end
  local filtered={}
  local search=string.lower(self.plannerSearch:GetText() or "")
  for _,row in ipairs(rows) do
    if search=="" or string.find(string.lower(row.name),search,1,true) or tostring(row.id)==search then filtered[#filtered+1]=row end
  end
  self.plannerPage=math.max(1,math.min(self.plannerPage or 1,math.max(1,math.ceil(#filtered/12))))
  local start=(self.plannerPage-1)*12
  for i,b in ipairs(self.plannerRows) do
    local row=filtered[start+i]; b:SetShown(row~=nil)
    if row then
      local label=row.group and checklistLabels[row.group] or row.priority==1 and "Urgent" or "Watch"
      b:SetText(label..": "..row.name)
      b:SetScript("OnClick",function() self.plannerQuest=row.id; self.plannerScroll:SetVerticalScroll(0); self:_RefreshPlanner() end)
    end
  end
  self.plannerPrevious:SetShown(start>0); self.plannerNext:SetShown(start+12<#filtered)
  local selected
  for _,row in ipairs(filtered) do if row.id==self.plannerQuest then selected=row; break end end
  if not selected then self.plannerQuest=nil end
  local lines={}
  if travel then
    lines={Addon.modules.Travel:Summary(),"", "Current route:"}
    local action=Addon.modules.Router.plan[1]
    lines[#lines+1]=action and ((Addon:GetQuest(action.questID).name).."\n"..(Addon.modules.Navigation:TravelHint() or Addon.modules.Navigation:Description())) or "No current action."
    local names={}
    for _,node in pairs(Addon.charDB.travel.nodes) do names[#names+1]=node.name..(node.point and " (located)" or " (visit to locate)") end
    table.sort(names)
    lines[#lines+1]="\nRemembered stops:\n"..table.concat(names,"\n")
  elseif selected then
    local q=Addon:GetQuest(selected.id)
    lines={q.name.." ("..q.id..")",e:GetResult(q.id).reason}
    if selected.group then lines[#lines+1]=checklistLabels[selected.group]..": "..selected.reason end
    local check=s:Check(q.id)
    if not check.allowed then lines[#lines+1]=check.reason end
    local risk=p.risks[q.id]
    if risk then
      lines[#lines+1]="\nPreserve this opportunity:"
      for _,reason in ipairs(risk.reasons) do lines[#lines+1]=reason end
      local consequences=p:Consequences(q.id)
      lines[#lines+1]="\n"..#consequences.." currently reachable dependent quests could also be lost:"
      for _,row in ipairs(consequences) do lines[#lines+1]=row.name end
    end
    local seen,id={},e:GetResult(q.id).blocker
    while id and not seen[id] do
      seen[id]=true; local dependency=Addon:GetQuest(id)
      lines[#lines+1]="Requires: "..(dependency and dependency.name or tostring(id))
      id=e:GetResult(id).blocker
    end
    lines[#lines+1]="\nInspect in dashboard for objectives, starter locations, and Skip/Restore."
  else
    lines={#filtered==0 and "No matching entries." or "Select a quest for details."}
    if mode=="checklist" then lines[#lines+1]="An empty local action list does not establish full zone completion. Review later, unknown, and filtered work before leaving." end
  end
  self.plannerDetails:SetText(table.concat(lines,"\n")); self.plannerChild:SetHeight(math.max(355,self.plannerDetails:GetStringHeight()+12))
  local q=self.plannerQuest and Addon:GetQuest(self.plannerQuest)
  if q and e:IsRoutable(q.id,true) and s:Check(q.id).allowed then self.plannerGuide:Enable() else self.plannerGuide:Disable() end
  if q then self.plannerInspect:Enable() else self.plannerInspect:Disable() end
end
StaticPopupDialogs.MADS_TBC_LOREMASTER_CHOICE={text="%s may close these quest opportunities:\n%s\n\nReview unfinished work before continuing in the quest window. This advisory performs no quest action.",button1=OKAY,timeout=0,whileDead=true,hideOnEscape=true,preferredIndex=3,
  OnAccept=function(_,data)
    if Addon.charDB and type(data)=="table" and Addon:IsID(data.questID) then
      local acknowledgments=data.turnIn and Addon.charDB.acknowledgedTurnIns or Addon.charDB.acknowledgedChoices
      acknowledgments[data.questID]=true
    end
  end}
function UI:MaybeWarnChoice(id,turnIn)
  if not Addon.charDB then return end
  local acknowledgments=turnIn and Addon.charDB.acknowledgedTurnIns or Addon.charDB.acknowledgedChoices
  if acknowledgments[id] then return end
  local q=Addon:GetQuest(id)
  if not q then return end
  local e=Addon.modules.Eligibility
  local names,seen={},{}
  local function add(other)
    local record=Addon:GetQuest(other)
    if record and not seen[other] and e:InFaction(record) and not e:CompletedOnce(other) then
      seen[other]=true; table.insert(names,record.name)
    end
  end
  for other in pairs(e.conflicts and e.conflicts[id] or {}) do add(other) end
  for other,record in pairs(e.records or {}) do
    if record.breadcrumbFor==id or record.nextQuest==id
      or (turnIn and (record.availableUntilCompleted==id or record.parentQuest==id)) then
      if e:IsRoutable(other,true) then add(other) end
    end
  end
  table.sort(names)
  if #names>0 then StaticPopup_Show("MADS_TBC_LOREMASTER_CHOICE",q.name,table.concat(names,", "),{questID=id,turnIn=turnIn}) end
end
