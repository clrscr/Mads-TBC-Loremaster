-- Executable Lua 5.1 regression tests. API doubles are deliberately local to
-- this process: they prove our logic, not Blizzard's live implementation.
local root=arg[1] or "."
local cases,passed={},0
local function test(name,fn) cases[#cases+1]={name,fn} end
local function eq(actual,expected,message)
  assert(actual==expected,(message or "unexpected value")..": expected "..tostring(expected)..", got "..tostring(actual))
end
local function contains(plan,id,kind)
  for _,a in ipairs(plan) do if a.questID==id and (not kind or a.type==kind) then return true end end
  return false
end
local A,E,R,C,N,api,timers,imports,errors
local function frame()
  local f={shown=true,scripts={},value="",width=300,height=200}
  local methods={}
  function methods:SetScript(k,v) self.scripts[k]=v end
  function methods:RegisterEvent(k) self[k]=true end
  function methods:UnregisterEvent(k) self[k]=nil end
  function methods:Show() self.shown=true; if self.scripts.OnShow then self.scripts.OnShow(self) end end
  function methods:Hide() self.shown=false end
  function methods:IsShown() return self.shown end
  function methods:SetShown(v) if v then self:Show() else self:Hide() end end
  function methods:SetText(v) self.value=v end
  function methods:GetText() return self.value end
  function methods:GetStringHeight() return math.ceil(#tostring(self.value)/45)*14 end
  function methods:GetFontString() return frame() end
  function methods:CreateFontString() return frame() end
  function methods:SetHeight(v) self.height=v end
  function methods:SetSize(w,h) self.width,self.height=w,h end
  function methods:GetPoint() return "CENTER",nil,"CENTER",0,0 end
  function methods:Enable() self.enabled=true end
  function methods:Disable() self.enabled=false end
  return setmetatable(f,{__index=function(_,k) return methods[k] or function() end end})
end
local function setup(records,characterSaved,accountSaved)
  MadsTBC={Manifest={quests=records or {},phase={number=2}}}
  MadsTBCLoremasterCharacterDB=characterSaved
  MadsTBCLoremasterDB=accountSaved
  Guidelime,TomTom=nil,nil
  api={completed={},active={},race="Human",raceID=1,class="WARRIOR",classID=1,faction="Alliance",level=20}
  timers,errors={},{}
  UIParent=frame(); SlashCmdList={}; StaticPopupDialogs={}; UISpecialFrames={}; OKAY="Okay"
  StaticPopup_Show=function(dialog,title,names,data) api.popup={dialog=dialog,title=title,names=names,data=data} end
  CreateFrame=frame
  geterrorhandler=function() return function(msg) errors[#errors+1]=msg end end
  strtrim=function(s) return s:match('^%s*(.-)%s*$') end
  C_Timer={After=function(delay,fn) timers[#timers+1]=fn end}
  GetBuildInfo=function() return "2.5.6","68575","Jul 2026",20506 end
  UnitRace=function() return api.race,api.race,api.raceID end
  UnitClass=function() return api.class,api.class,api.classID end
  UnitFactionGroup=function() return api.faction end
  UnitLevel=function() return api.level end
  GetQuestsCompleted=function() return api.completed end
  C_QuestLog={GetNumQuestLogEntries=function() return api.count or #api.active end,
    GetInfo=function(i) return api.active[i] end,
    IsComplete=function(id) for _,q in ipairs(api.active) do if q.questID==id then return q.complete end end end,
    GetQuestObjectives=function(id) for _,q in ipairs(api.active) do if q.questID==id then return q.objectives end end end}
  GetProfessions,GetProfessionInfo=nil,nil
  GetBindLocation,GetSubZoneText,GetZoneText,GetTime,GetItemCount,GetItemCooldown=nil,nil,nil,nil,nil,nil
  NumTaxiNodes,GetTaxiMapID,TaxiNodeName,TaxiNodeGetType=nil,nil,nil,nil
  C_Item,C_Container=nil,nil
  IsSpellKnown=function(id) return api.spells and api.spells[id] or false end
  imports={QuestieProfessions={GetPlayerProfessions=function() return {} end},
    QuestieReputation={GetPlayerReputations=function() return {} end},
    ZoneDB={GetAreaIdByUiMapId=function(_,id) if id==100 then return 12 end end,
      GetUiMapIdByAreaId=function(_,id) if id==12 then return 100 end end},
    QuestieEvent={calendarDataCached=true,IsEventActiveForQuest=function() return false end}}
  C_Map={GetBestMapForUnit=function() return 100 end,GetPlayerMapPosition=function() return {GetXY=function() return .5,.5 end} end}
  QuestieLoader={ImportModule=function(_,name) return imports[name] end}
  Questie={API={RegisterOnReady=function(fn) api.onReady=fn end,RegisterForQuestUpdates=function(fn) api.onUpdate=fn end}}
  assert(loadfile(root.."/Runtime/Core.lua"))("Mads_TBCLoremaster",{})
  A=MadsTBC
  for _,name in ipairs({"Character","Eligibility","Selection","Planning","Travel","Router","Navigation","GuideCompat","UI"}) do dofile(root.."/Runtime/"..name..".lua") end
  A.GetLore=function() end
  A:NormalizeSavedVariables()
  for _,name in ipairs({"Character","Eligibility","Selection","Planning","Travel","Router","Navigation"}) do A.modules[name]:Initialize() end
  E,R,C,N=A.modules.Eligibility,A.modules.Router,A.modules.Character,A.modules.Navigation
end
local function q(id,fields)
  local row={id=id,name="Quest "..id,permanent=true,canonicalZone=12,zoneName="Elwynn Forest",requiredLevel=1,questLevel=10,requiredRaces=0,requiredClasses=0}
  for k,v in pairs(fields or {}) do row[k]=v end
  return row
end
local function scan()
  assert(C:Scan()); E:Rebuild(); R:Refresh()
end
local function tick()
  local pending=timers; timers={}
  for _,fn in ipairs(pending) do fn() end
end

test("malformed saved settings migrate without inventing completions",function()
  setup({[1]=q(1)},{schemaVersion=1,routeQuestIDs={1,2},routeIndex=2,deferred="bad",recurringHistory={[1]=true,bad=true},discovered="bad"},
    {window={point="INVALID",x=0/0,y="bad"},phaseOverride=2.5,detailLevel="bad"})
  eq(A.db.window.point,"CENTER"); eq(A.db.window.x,0); eq(A.db.phaseOverride,nil)
  eq(A.charDB.resumeQuestID,2); eq(next(A.charDB.completedEvidence),nil); eq(#A.charDB.routeQuestIDs,0)
  eq(A.charDB.recurringHistory.bad,nil); eq(A.charDB.recurringHistory[1],true)
  MadsTBCLoremasterCharacterDB=false; MadsTBCLoremasterDB="bad"; A:NormalizeSavedVariables()
  eq(A.charDB.journey.mode,"journey")
end)
test("login waits for Questie and coalesces updates",function()
  setup({[1]=q(1)}); A.modules.UI.Initialize=function() end
  A:Initialize(); A:Rescan("QUEST_LOG_UPDATE"); eq(#timers,0); eq(#R.plan,0)
  api.onReady(); api.onUpdate(); api.onUpdate(); eq(#timers,1)
  tick(); eq(C.snapshot.ready,true); eq(#R.plan,1); eq(A.charDB.firstScanComplete,true)
  eq(#errors,0)
end)
test("incomplete scan preserves route and snapshot with bounded retries",function()
  setup({[1]=q(1)}); scan(); local snapshot=C.snapshot
  A.initialized,A.questieReady=true,true; api.completed=nil
  A:Rescan("manual"); tick(); eq(C.snapshot,snapshot); eq(R.plan[1].questID,1)
  for i=1,8 do tick() end
  eq(#timers,0); assert(A.status)
end)
test("delayed quest-log rows never masquerade as an empty log",function()
  setup({[1]=q(1)}); scan(); local snapshot=C.snapshot; api.count=1
  eq(C:Scan(),false); eq(C.snapshot,snapshot)
end)
test("race class and faction scopes differ from completionist scope",function()
  setup({[1]=q(1),[2]=q(2,{requiredRaces=2}),[3]=q(3,{requiredRaces=8}),[4]=q(4,{requiredClasses=128})}); scan()
  eq(E:GetState(2),"ineligible_faction"); eq(E:GetState(3),"ineligible_race"); eq(E:GetState(4),"ineligible_class")
  eq(E.summary.completionistTotal,3); eq(E.summary.achievableTotal,1)
  api.faction,api.race,api.raceID="Horde","Orc",2; scan(); eq(E:GetState(2),"available"); eq(E.summary.completionistTotal,3)
end)
test("context variants replace and clear facts",function()
  setup({[1]=q(1,{requiredClasses=128,variants={{contexts={"Alliance:WARRIOR:Human"},fields={name="Human warrior"},clear={"requiredClasses"}}}})}); scan()
  eq(A:GetQuest(1).name,"Human warrior"); eq(E:GetState(1),"available")
  api.class,api.classID="ROGUE",4; scan(); eq(E:GetState(1),"ineligible_class")
end)
test("unreachable and unknown prerequisites propagate past local rank blockers",function()
  setup({[1]=q(1,{requiredClasses=128}),[2]=q(2,{prerequisitesAll={1},requiredSkill={171,50}}),[3]=q(3,{prerequisitesAny={999}})})
  imports.QuestieProfessions.GetPlayerProfessions=function() return {[171]={"Alchemy",1}} end
  scan(); eq(E:GetState(2),"unreachable_dependency"); eq(E:GetState(3),"unknown_dependency")
  eq(E.summary.achievableTotal,0); eq(#R.plan,0)
end)
test("cycles are unresolved rather than actionable",function()
  setup({[1]=q(1,{prerequisitesAll={2}}),[2]=q(2,{prerequisitesAll={1}})}); scan()
  eq(E:GetState(1),"unknown_dependency"); eq(E:GetState(2),"unknown_dependency"); eq(#R.plan,0)
end)
test("all-of, any-of, negative exact and exclusive-equivalent prerequisites",function()
  setup({[1]=q(1,{exclusiveTo={2}}),[2]=q(2),[3]=q(3,{prerequisitesAll={1}}),[4]=q(4,{prerequisitesAll={-1}}),[5]=q(5,{prerequisitesAll={999},prerequisitesAny={2}})})
  api.completed[2]=true; scan()
  eq(E:GetState(3),"available"); eq(E:GetState(4),"unreachable_dependency"); eq(E:GetState(5),"available")
end)
test("parent goals route children while parent stays active",function()
  setup({[1]=q(1),[2]=q(2,{parentQuest=1})}); api.active={{questID=1,title="Parent"}}; scan(); R:Start("quest",nil,1)
  eq(R.plan[1].questID,2); eq(R.plan[1].type,"accept")
  api.completed[2]=true; scan(); eq(R.plan[1].questID,1); eq(R.plan[1].type,"objective")
  api.active={}; api.completed[1]=true; api.completed[2]=nil; scan(); eq(E:GetState(2),"permanently_locked")
end)
test("available-starting-with accepts an active enabling quest",function()
  setup({[1]=q(1),[2]=q(2,{enabledBy=1})}); api.active={{questID=1}}; scan()
  eq(E:GetState(2),"available")
end)
test("quest goals expand a reachable any-of bridge",function()
  setup({[1]=q(1,{requiredClasses=128}),[2]=q(2),[3]=q(3,{prerequisitesAny={1,2}})}); scan(); R:Start("quest",nil,3)
  eq(#R.plan,1); eq(R.plan[1].questID,2)
end)
test("compatible projection favors more reachable descendants without double counting",function()
  setup({[1]=q(1,{exclusiveTo={2}}),[2]=q(2),[3]=q(3,{prerequisitesAny={2}}),[4]=q(4,{prerequisitesAny={1,2}})}); scan()
  eq(E.summary.completionistTotal,4); eq(E.summary.achievableTotal,3)
  eq(E:IsRecommendedChoice(1),false); eq(E:IsRecommendedChoice(2),true)
  api.completed[1]=true; scan(); eq(E.summary.achievableTotal,2); eq(E.summary.achievableCompleted,1)
end)
test("observed conflicting completions are never erased",function()
  setup({[1]=q(1,{exclusiveTo={2}}),[2]=q(2)}); api.completed={[1]=true,[2]=true}; scan()
  eq(E.summary.achievableTotal,2); eq(E.summary.achievableCompleted,2)
end)
test("profession slots after holes and missing private data are handled",function()
  setup({[1]=q(1,{requiredSkill={185,50}})})
  GetProfessions=function() return nil,nil,3,nil,5 end
  GetProfessionInfo=function(index) return "skill",nil,75,nil,nil,nil,index==3 and 185 or 129 end
  scan(); eq(E:GetState(1),"available"); eq(C.snapshot.professions[129],75)
  imports.QuestieProfessions=nil; scan(); eq(E:GetState(1),"unknown_requirement")
end)
test("signed skill spell reputation and level restrictions",function()
  setup({[1]=q(1,{requiredRanks={{762,-125}}}),[2]=q(2,{requiredSpell=-123}),[3]=q(3,{requiredMaxRep={932,3000}}),[4]=q(4,{maximumLevel=10})})
  imports.QuestieProfessions.GetPlayerProfessions=function() return {[762]={"Riding",125}} end
  imports.QuestieReputation.GetPlayerReputations=function() return {[932]={4,3000}} end
  api.spells={[123]=true}; scan()
  for id=1,4 do eq(E:GetState(id),"permanently_locked") end
end)
test("phase and event uncertainty are explicit and recover dynamically",function()
  setup({[1]=q(1,{availabilityByPhase={"future","future","current","current","current"}}),[2]=q(2,{eventOnly=true})})
  imports.QuestieEvent.calendarDataCached=false; scan(); eq(E:GetState(1),"temporarily_unavailable"); eq(E:GetState(2),"unknown_availability")
  A.db.phaseOverride=3; imports.QuestieEvent.calendarDataCached=true; scan(); eq(E:GetState(1),"available"); eq(E:GetState(2),"temporarily_unavailable_event")
  imports.QuestieEvent.IsEventActiveForQuest=function() return true end; scan(); eq(E:GetState(2),"available")
end)
test("recurring first completions survive resets but optional runs remain",function()
  setup({[1]=q(1,{permanent=false})}); scan(); eq(#R.plan,1)
  A:RecordTurnIn(1); scan(); eq(E.summary.achievableCompleted,1); eq(#R.plan,0)
  R:Start("recurring"); eq(#R.plan,1); eq(R.plan[1].questID,1)
  eq(A.charDB.completedEvidence[1],nil)
end)
test("permanent turn-in evidence bridges a lagging completion API",function()
  setup({[1]=q(1)}); scan(); A:RecordTurnIn(1); scan(); eq(E:GetState(1),"completed"); eq(#R.plan,0)
end)
test("defer preserves totals and restore resumes unfinished work",function()
  setup({[1]=q(1),[2]=q(2,{prerequisitesAll={1}})}); scan(); local total=E.summary.achievableTotal
  R:Defer(1); eq(#R.plan,0); scan(); eq(E.summary.achievableTotal,total); eq(E.summary.deferred,1)
  A.charDB.deferred[1]=nil; scan(); eq(R.plan[1].questID,1)
end)
test("live objective transitions advance to turn-in and onward",function()
  setup({[1]=q(1),[2]=q(2,{prerequisitesAll={1}})})
  api.active={{questID=1,objectives={{text="First",finished=true},{text="Second",finished=false}}}}; scan()
  eq(R.plan[1].objectiveIndex,2); eq(R.plan[1].text,"Second")
  api.active[1].complete=true; scan(); eq(R.plan[1].type,"turn_in")
  api.active={}; api.completed[1]=true; scan(); eq(R.plan[1].questID,2); eq(R.plan[1].type,"accept")
end)
test("quest-log reserve blocks pickups without abandoning active work",function()
  local records={[1]=q(1)}; setup(records)
  for id=2,24 do records[id]=q(id); api.active[#api.active+1]={questID=id} end
  scan(); eq(contains(R.plan,1,"accept"),false); eq(#R.plan,23)
end)
test("catchup ignores negative level sentinels and includes gray quests",function()
  setup({[1]=q(1,{questLevel=-1,requiredLevel=25}),[2]=q(2,{questLevel=1})}); scan(); R:Start("catchup")
  eq(#R.plan,1); eq(R.plan[1].questID,2)
end)
test("reload keeps a useful action and migration respects current state",function()
  setup({[1]=q(1),[2]=q(2)},{schemaVersion=2,currentActionKey="accept:2:0"}); scan(); eq(R.plan[1].questID,2)
  api.completed[2]=true; scan(); eq(R.plan[1].questID,1)
end)
test("missable opportunities take priority over retained action",function()
  setup({[1]=q(1),[2]=q(2,{maximumLevel=30})},{schemaVersion=2,currentActionKey="accept:1:0"}); scan(); eq(R.plan[1].questID,2)
end)
test("same-zone endpoint distance orders new actions",function()
  local function starter(x) return {{kind="npc",points={{areaId=12,x=x,y=50}}}} end
  setup({[1]=q(1,{starters=starter(90)}),[2]=q(2,{starters=starter(51)})}); scan(); eq(R.plan[1].questID,2)
end)
test("waypoints use map conversion, deduplicate, and clear on unavailable destinations",function()
  setup({[1]=q(1,{starters={{kind="npc",points={{areaId=12,x=50,y=50}}}}}),[2]=q(2)})
  local added,removed=0,0
  TomTom={AddWaypoint=function(_,map,x,y) eq(map,100); added=added+1; return "owned" end,
    RemoveWaypoint=function(_,uid) eq(uid,"owned"); removed=removed+1 end}
  scan(); eq(added,1); R:Refresh(); eq(added,1)
  N:SetForAction({questID=2,type="accept",key="accept:2:0"}); eq(removed,1); eq(N.tomtomUID,nil)
  imports.ZoneDB.GetUiMapIdByAreaId=function() end
  N:SetForAction({questID=1,type="accept",key="accept:1:0"}); eq(added,1)
end)
test("missing map conversion does not substitute an AreaID or UiMapID",function()
  setup({[1]=q(1)}); imports.ZoneDB=nil; scan(); eq(C.snapshot.currentAreaID,nil); eq(N:_UiMapID(12),nil)
end)
test("uncatalogued live quests remain visible without invented starters",function()
  setup({}); api.active={{questID=99999,title="Observed quest",level=12}}; scan()
  eq(E:GetState(99999),"active"); eq(A:GetQuest(99999).name,"Observed quest"); eq(#R.plan,1)
  api.active={}; scan(); eq(E:GetState(99999),"unknown_availability")
end)
test("compatibility bridge never impersonates Guidelime",function()
  setup({}); A.RegisterLegacyGuide("guide","group"); eq(Guidelime,nil); eq(#A.LegacyGuides,1)
  local called=false; Guidelime={registerGuide=function(text,group) eq(text,"guide"); eq(group,"group"); called=true end}
  A.RegisterLegacyGuide("guide","group"); eq(called,true)
end)
test("dashboard supports empty state, all pages and recurring selection",function()
  setup({[1]=q(1,{permanent=false}),[2]=q(2)})
  local ui=A.modules.UI; ui:Initialize(); ui.dashboard:Show(); ui:Refresh(); scan()
  for _,page in ipairs({"overview","quests","zones","recurring","settings"}) do ui:SetPage(page) end
  ui:SetPage("recurring"); eq(#ui:_Rows(),1); ui.zoneRows[1].scripts.OnClick(); eq(ui.selectedQuest,1)
  ui.goalButton.scripts.OnClick(); eq(A.charDB.journey.questID,1)
  ui:MaybeWarnChoice(1); eq(#errors,0)
end)
test("unchanged objective events skip eligibility and route rebuilding",function()
  setup({[1]=q(1)}); scan(); A.initialized,A.questieReady=true,true
  local count=0; local rebuild=E.Rebuild
  E.Rebuild=function(self) count=count+1; return rebuild(self) end
  A:Rescan("QUEST_LOG_UPDATE"); tick(); eq(count,0)
  api.active={{questID=1,objectives={{text="Progress 1/2",finished=false}}}}
  A:Rescan("QUEST_LOG_UPDATE"); tick(); eq(count,1)
  A:Rescan("QUEST_LOG_UPDATE"); tick(); eq(count,1)
end)
test("unsupported clients wait without scanning",function()
  setup({[1]=q(1)}); A.modules.UI.Initialize=function() end
  GetBuildInfo=function() return "unknown","unknown","unknown",99999 end
  A:Initialize(); eq(api.onReady,nil); assert(A.status:find("20506",1,true)); eq(#R.plan,0)
end)
test("recurring active state wins over a retained completion flag",function()
  setup({[1]=q(1,{permanent=false})}); api.completed[1]=true; api.active={{questID=1}}
  scan(); eq(E:GetState(1),"active"); eq(E.summary.achievableCompleted,1); eq(R.plan[1].type,"objective")
end)
test("discovered settings sanitize malformed record values",function()
  setup({},{discovered={[7]={name={},faction="Alliance",level="bad"},[8]={name="No faction"}}}); scan()
  eq(A:GetQuest(7).questLevel,1); eq(A.charDB.discovered[8],nil)
end)

test("logged quests remain actionable with missing source prerequisites",function()
  setup({[1]=q(1,{prerequisitesAll={999}})}); api.active={{questID=1}}
  scan(); eq(E:GetState(1),"active"); eq(#R.plan,1)
end)
test("objective source order does not invent a target association",function()
  setup({[1]=q(1,{objectives={{kind="npc",name="Different target",points={{areaId=12,x=10,y=10}}},{kind="npc",name="Target",points={{areaId=12,x=50,y=50}}}}})})
  api.active={{questID=1,objectives={{type="monster",text="Target slain: 0/1",finished=false},{type="monster",text="Other slain: 0/1",finished=false}}}}
  scan(); local point=N:_PointForAction({questID=1,type="objective",objectiveIndex=1})
  eq(point.x,50)
  eq(N:_PointForAction({questID=1,type="objective",objectiveIndex=2}),nil)
end)
test("explicit child associations guide interactions without inventing parent gates",function()
  setup({[1]=q(1,{children={2}}),[2]=q(2,{permanent=false})}); api.active={{questID=1}}
  scan(); R:Start("quest",nil,1); eq(R.plan[1].questID,2); eq(E:GetState(2),"available")
  A:RecordTurnIn(2); scan(); eq(R.plan[1].questID,1)
end)
test("acceptance acknowledgment does not suppress a later turn-in warning",function()
  setup({[1]=q(1),[2]=q(2,{parentQuest=1}),[3]=q(3,{availableUntilCompleted=1})})
  api.active={{questID=1,complete=true}}; scan(); A.charDB.acknowledgedChoices[1]=true
  A.modules.UI:MaybeWarnChoice(1,true)
  assert(api.popup.names:find("Quest 2",1,true)); assert(api.popup.names:find("Quest 3",1,true))
  StaticPopupDialogs.MADS_TBC_LOREMASTER_CHOICE.OnAccept(nil,api.popup.data)
  eq(A.charDB.acknowledgedTurnIns[1],true)
end)
test("category inclusion is OR, exclusions win and reset is independent of skips",function()
  setup({[1]=q(1,{category="dungeon"}),[2]=q(2,{category="profession"}),[3]=q(3),[4]=q(4,{category="profession",kinds={"dungeon"}})})
  scan(); local s=A.modules.Selection
  s:SetCategory("dungeon","include"); eq(#R.plan,2); eq(s.summary.completionistTotal,2)
  s:SetCategory("profession","include"); eq(#R.plan,3); eq(s.summary.completionistTotal,3)
  s:SetCategory("profession","exclude"); eq(#R.plan,1); eq(R.plan[1].questID,1)
  s:SetCategory("dungeon","any"); eq(#R.plan,2); eq(contains(R.plan,3),true)
  R:Skip(1); s:ResetCategories(); eq(A.charDB.deferred[1],true); eq(#R.plan,3)
  eq(E.summary.completionistTotal,4); eq(E.summary.achievableTotal,4)
end)
test("category facets preserve class skill heroic PvP and event distinctions",function()
  setup({}); local s=A.modules.Selection
  assert(s:Categories(q(1,{category="profession",kinds={"dungeon","heroic"}})).dungeon)
  assert(s:Categories(q(2,{requiredClasses=128})).class)
  eq(s:Categories(q(3,{requiredClasses=1503})).class,false)
  assert(s:Categories(q(4,{requiredRanks={{762,-125}}})).profession)
  assert(s:Categories(q(5,{kinds={"pvp","world"}})).pvp)
  eq(s:Categories(q(5,{kinds={"pvp","world"}})).general,false)
  eq(s:Categories(q(6,{kinds={"scripted_or_event"}})).event,false)
  assert(s:Categories(q(7,{kinds={"seasonal_or_event"}})).event)
  assert(s:Categories(q(8,{category="unknown"})).unknown)
  eq(s:Categories(q(8,{category="unknown"})).general,false)
end)
test("category preferences normalize and survive mode changes and reload",function()
  local records={[1]=q(1,{category="dungeon"}),[2]=q(2)}
  setup(records,{deferred={[2]=true},categoryPreferences={dungeon="include",profession="exclude",bad="include",raid=true}})
  scan(); local s=A.modules.Selection
  eq(A.charDB.categoryPreferences.bad,nil); eq(A.charDB.categoryPreferences.raid,nil)
  R:Start("catchup"); R:Start("back_on_track"); eq(A.charDB.categoryPreferences.dungeon,"include")
  local saved=A:Copy(A.charDB); setup(records,saved); scan()
  eq(#R.plan,1); eq(A.charDB.deferred[2],true); eq(A.charDB.categoryPreferences.profession,"exclude")
  MadsTBCLoremasterCharacterDB.categoryPreferences="bad"; A:NormalizeSavedVariables(); eq(next(A.charDB.categoryPreferences),nil)
end)
test("required bridges appear outside includes and do not inflate category subtotals",function()
  setup({[1]=q(1,{canonicalZone=40,zoneName="Westfall"}),[2]=q(2,{category="dungeon",prerequisitesAll={1}})})
  scan(); local s=A.modules.Selection; s:SetCategory("dungeon","include")
  eq(R.plan[1].questID,1); eq(s.bridges[1],2); eq(s.summary.completionistTotal,1)
  eq(s.summary.achievableTotal,1); eq(s.zones[40].completionistTotal,0); eq(s.zones[40].bridges,1)
  local ui=A.modules.UI; ui:Initialize(); ui.dashboard:Show(); ui:Refresh(); ui.selectedZone=12; ui:SetPage("quests")
  eq(#ui:_Rows(),2); assert(ui.trackerMeta.value:find("Required prerequisite for Quest 2",1,true))
  ui.selectedQuest=1; ui:_Details(); assert(ui.details.value:find("Required prerequisite for Quest 2",1,true))
end)
test("excluded and skipped prerequisite chains explain preference blocks",function()
  setup({[1]=q(1,{category="profession"}),[2]=q(2,{prerequisitesAll={1}}),[3]=q(3,{category="dungeon",prerequisitesAll={2}}),[4]=q(4,{category="dungeon"})})
  scan(); local s=A.modules.Selection; s:SetCategory("dungeon","include"); s:SetCategory("profession","exclude")
  eq(#R.plan,1); eq(R.plan[1].questID,4); eq(s:Check(3).allowed,false); eq(s:Check(3).blocker,1)
  eq(E:GetState(3),"prerequisite_blocked")
  R:Start("quest",nil,3); eq(#R.plan,0); assert(R.explanation:find("Excluded category",1,true))
  s:SetCategory("profession","any"); eq(R.plan[1].questID,1)
  R:Skip(1); eq(#R.plan,0); assert(R.explanation:find("Skipped quest: Quest 1",1,true))
  R:Restore(1); eq(R.plan[1].questID,1)
end)
test("any-of bridges try a permitted alternative before declaring a block",function()
  setup({[1]=q(1,{category="profession"}),[2]=q(2),[3]=q(3,{category="dungeon",prerequisitesAny={1,2}})})
  scan(); local s=A.modules.Selection; s:SetCategory("dungeon","include"); s:SetCategory("profession","exclude")
  eq(#R.plan,1); eq(R.plan[1].questID,2); eq(s.bridges[2],3)
  R:Skip(2); eq(#R.plan,0); eq(s:Check(3).allowed,false)
end)
test("completed or active enabling requirements stay satisfied despite preferences",function()
  setup({[1]=q(1,{category="profession"}),[2]=q(2,{category="dungeon",prerequisitesAll={1}}),[3]=q(3,{category="profession"}),[4]=q(4,{category="dungeon",parentQuest=3}),[5]=q(5,{category="dungeon",enabledBy=3})})
  api.completed[1]=true; api.active={{questID=3}}; scan()
  local s=A.modules.Selection; R:Skip(1); R:Skip(3); s:SetCategory("profession","exclude"); s:SetCategory("dungeon","include")
  eq(contains(R.plan,2,"accept"),true); eq(contains(R.plan,4,"accept"),true); eq(contains(R.plan,5,"accept"),true)
  eq(contains(R.plan,3),false)
end)
test("skipping an active child blocks parent guidance without stalling other work",function()
  setup({[1]=q(1,{category="dungeon"}),[2]=q(2,{parentQuest=1}),[3]=q(3,{category="dungeon"})})
  api.active={{questID=1},{questID=2}}; scan(); local s=A.modules.Selection; s:SetCategory("dungeon","include")
  R:Skip(2); eq(contains(R.plan,1),false); eq(contains(R.plan,2),false); eq(R.plan[1].questID,3)
  eq(s:Check(1).blocker,2); R:Restore(2); eq(contains(R.plan,2),true)
end)
test("active quests still respect their own exclusions but not stale prerequisites",function()
  setup({[1]=q(1,{category="profession"}),[2]=q(2,{category="dungeon",prerequisitesAll={1}})})
  api.active={{questID=1,complete=true},{questID=2}}; scan()
  A.modules.Selection:SetCategory("profession","exclude")
  eq(contains(R.plan,1),false); eq(contains(R.plan,2),true)
  A.modules.Selection:SetCategory("dungeon","exclude"); eq(#R.plan,0)
end)
test("skip survives reload and no journey command silently restores it",function()
  local records={[1]=q(1,{category="dungeon"}),[2]=q(2)}
  setup(records); scan(); R:Skip(1); R:Start("quest",nil,1); eq(#R.plan,0)
  local saved=A:Copy(A.charDB); setup(records,saved); scan(); eq(contains(R.plan,1),false)
  R:Restore(1); eq(R.plan[1].questID,1); eq(E.summary.completionistCompleted,0)
end)
test("restoring skips leaves exclusions and recurring history untouched",function()
  setup({[1]=q(1,{category="dungeon",permanent=false})})
  scan(); A:RecordTurnIn(1); scan(); R:Start("recurring"); R:Skip(1)
  local s=A.modules.Selection; s:SetCategory("dungeon","exclude"); R:RestoreAll()
  eq(#R.plan,0); eq(A.charDB.recurringHistory[1],true); eq(E.summary.achievableCompleted,1)
  s:ResetCategories(); eq(#R.plan,1); eq(s.summary.achievableCompleted,1)
end)
test("preference changes rebuild immediately without scanning or solving global choices",function()
  setup({[1]=q(1,{category="dungeon"}),[2]=q(2)}); scan()
  C.Scan=function() error("must not rescan") end
  E.Rebuild=function() error("must not rebuild global projection") end
  local generation=C.snapshot.generation
  A.modules.Selection:SetCategory("dungeon","include"); eq(#R.plan,1)
  R:SkipCurrent(); eq(#R.plan,0); R:RestoreAll(); eq(#R.plan,1)
  eq(C.snapshot.generation,generation); eq(#timers,0)
end)
test("selected category subtotals count overlaps once and preserve unfinished skips",function()
  setup({[1]=q(1,{category="profession",kinds={"dungeon"},permanent=false}),[2]=q(2,{category="dungeon"}),[3]=q(3)})
  scan(); A:RecordTurnIn(1); scan(); local s=A.modules.Selection
  s:SetCategory("profession","include"); s:SetCategory("dungeon","include"); R:Skip(2)
  eq(s.summary.completionistTotal,2); eq(s.summary.completionistCompleted,1)
  eq(s.summary.achievableTotal,2); eq(s.summary.achievableCompleted,1)
  eq(E.summary.completionistTotal,3); eq(E.summary.achievableTotal,3); eq(s.skipped,1)
end)
test("UI category controls act on their own category and show selected states",function()
  setup({[1]=q(1,{category="dungeon"}),[2]=q(2,{category="profession"})}); scan()
  local ui=A.modules.UI; ui:Initialize(); ui.dashboard:Show(); ui.categoryButton.scripts.OnClick()
  ui.categoryControls.dungeon.include.scripts.OnClick()
  eq(A.charDB.categoryPreferences.dungeon,"include"); eq(ui.categoryControls.dungeon.include.enabled,false)
  ui.categoryControls.profession.exclude.scripts.OnClick()
  eq(A.charDB.categoryPreferences.profession,"exclude"); eq(A.charDB.categoryPreferences.dungeon,"include")
  assert(ui.categorySummary.value:find("Exclude: Profession",1,true))
  ui.resetCategories.scripts.OnClick(); eq(next(A.charDB.categoryPreferences),nil)
end)
test("skipped management bypasses categories, zone and recurring view filters",function()
  setup({[1]=q(1,{category="profession",canonicalZone=40}),[2]=q(2,{category="dungeon"})}); scan()
  R:Skip(1); A.modules.Selection:SetCategory("profession","exclude")
  local ui=A.modules.UI; ui:Initialize(); ui.dashboard:Show(); ui.filter="skipped"; ui.selectedZone=12; ui:SetPage("recurring")
  eq(#ui:_Rows(),1); eq(ui:_Rows()[1].id,1)
  ui.selectedQuest=1; ui:_RefreshDashboard(); eq(ui.goalButton.enabled,false); eq(ui.deferSelected.value,"Restore")
  ui.deferSelected.scripts.OnClick(); eq(A.charDB.deferred[1],nil); eq(contains(R.plan,1),false)
end)
test("explicit excluded goals explain the exclusion and preserve completion",function()
  setup({[1]=q(1,{category="dungeon"})}); scan(); local s=A.modules.Selection
  s:SetCategory("dungeon","exclude"); R:Start("quest",nil,1)
  eq(#R.plan,0); assert(R.explanation:find("Excluded category: Dungeon",1,true))
  eq(E:GetState(1),"available"); eq(E.summary.completionistTotal,1); eq(E.summary.completionistCompleted,0)
end)
test("category switches replace or clear only the owned waypoint",function()
  local function starter(x) return {{kind="npc",points={{areaId=12,x=x,y=50}}}} end
  setup({[1]=q(1,{category="dungeon",starters=starter(50)}),[2]=q(2,{category="profession",starters=starter(51)})})
  local added,removed=0,0
  TomTom={AddWaypoint=function() added=added+1; return added end,RemoveWaypoint=function() removed=removed+1 end}
  scan(); eq(added,1); A.modules.Selection:SetCategory("dungeon","exclude")
  eq(added,2); eq(removed,1); eq(R.plan[1].questID,2)
  A.modules.Selection:SetCategory("profession","exclude"); eq(removed,2); eq(N.tomtomUID,nil); eq(#R.plan,0)
end)

test("skip advances from active and turn-in-ready quests without abandoning or completing",function()
  for _,complete in ipairs({false,true}) do
    setup({[1]=q(1),[2]=q(2)}); api.active={{questID=1,complete=complete}}; scan()
    eq(R.plan[1].questID,1); R:SkipCurrent(); eq(R.plan[1].questID,2)
    eq(#api.active,1); eq(E.summary.completionistCompleted,0)
    eq(E:GetState(1),complete and "ready_to_turn_in" or "active")
    R:Restore(1); eq(contains(R.plan,1),true)
  end
end)
test("Restore and guide explicitly clears a skip and focuses the selected quest",function()
  setup({[1]=q(1),[2]=q(2)}); scan(); R:Skip(1)
  local ui=A.modules.UI; ui:Initialize(); ui.dashboard:Show(); ui.filter="skipped"; ui.selectedQuest=1; ui:_RefreshDashboard()
  eq(ui.goalButton.value,"Restore and guide"); eq(ui.goalButton.enabled,true)
  ui.goalButton.scripts.OnClick(); eq(A.charDB.deferred[1],nil); eq(R.plan[1].questID,1)
  eq(A.charDB.journey.mode,"quest"); eq(E.summary.completionistCompleted,0)
end)
test("an empty category selection explains recovery instead of inventing progress",function()
  setup({[1]=q(1),[2]=q(2,{category="dungeon"})}); scan()
  local s=A.modules.Selection
  for _,category in ipairs(s.categories) do s:SetCategory(category[1],"exclude") end
  eq(#R.plan,0); eq(s.summary.completionistTotal,0); eq(E.summary.completionistTotal,2)
  assert(R.explanation:find("Open Categories",1,true))
  s:ResetCategories(); eq(#R.plan,2)
end)
test("packaged catalog loads and plans for every supported race and class",function()
  setup({}); dofile(root.."/data/QuestManifest.lua")
  local count=0; for _ in pairs(A.Manifest.quests) do count=count+1 end; assert(count>6350)
  local combinations={
    {"Alliance","Human",1,{1,2,4,5,8,9}}, {"Alliance","Dwarf",3,{1,2,3,4,5}},
    {"Alliance","NightElf",4,{1,3,4,5,11}}, {"Alliance","Gnome",7,{1,4,8,9}},
    {"Alliance","Draenei",11,{1,2,3,5,7,8}}, {"Horde","Orc",2,{1,3,4,7,9}},
    {"Horde","Scourge",5,{1,4,5,8,9}}, {"Horde","Tauren",6,{1,3,7,11}},
    {"Horde","Troll",8,{1,3,4,5,7,8}}, {"Horde","BloodElf",10,{2,3,4,5,8,9}}}
  local classes={[1]="WARRIOR",[2]="PALADIN",[3]="HUNTER",[4]="ROGUE",[5]="PRIEST",[7]="SHAMAN",[8]="MAGE",[9]="WARLOCK",[11]="DRUID"}
  local facets=A.modules.Selection:Categories(A.Manifest.quests[5306])
  assert(facets.dungeon and facets.profession,"Packaged Snakestone quest must match both categories")
  local start=os.clock(); local profiles,filteredProfiles=0,0
  for _,race in ipairs(combinations) do
    api.faction,api.race,api.raceID=race[1],race[2],race[3]
    for _,class in ipairs(race[4]) do
      api.classID,api.class=class,classes[class]
      for _,level in ipairs({1,70}) do
        api.level=level; R.currentKey=nil; scan(); profiles=profiles+1
        assert(E.summary.completionistTotal>3500)
        assert(E.summary.achievableTotal<=E.summary.completionistTotal)
        assert(E.summary.achievableCompleted<=E.summary.achievableTotal)
        assert(#R.plan>0,"No journey for "..api.race.." "..api.class.." "..level)
        if level==70 then
          local overall=E.summary.achievableTotal
          local selection=A.modules.Selection
          selection:SetCategory("dungeon","include")
          selection:SetCategory("profession","exclude")
          for _,action in ipairs(R.plan) do
            local record=A:GetQuest(action.questID)
            eq(selection:Excluded(record),nil,"Filtered corpus action must respect exclusions")
            assert(selection:Matches(record) or selection.bridges[record.id],"Outside-category action must explain its prerequisite role")
          end
          eq(E.summary.achievableTotal,overall)
          assert(selection.summary.achievableTotal<=overall)
          filteredProfiles=filteredProfiles+1
          selection:ResetCategories()
        end
      end
    end
  end
  print(string.format("  catalog: %d records, %d character/level profiles, %d filtered journeys, %.2fs CPU",count,profiles,filteredProfiles,os.clock()-start))
end)

local function endpoint(area,x,y)
  return {{kind="npc",name="Quest giver",points={{areaId=area,x=x or 50,y=y or 50}}}}
end
test("departure checklist includes local endpoints for quests cataloged elsewhere",function()
  setup({[1]=q(1,{canonicalZone=40,starters=endpoint(12)}),[2]=q(2,{canonicalZone=40,finishers=endpoint(12)}),
    [3]=q(3,{objectives=endpoint(12)}),[4]=q(4,{requiredLevel=60}),[5]=q(5,{unknownAvailability=true}),
    [6]=q(6,{requiredClasses=128}),[7]=q(7,{maximumLevel=2}),[8]=q(8,{prerequisitesAll={4}})})
  api.active={{questID=2,complete=true},{questID=3}}; scan()
  local rows,counts=A.modules.Planning:Checklist(12)
  eq(#rows,7); eq(counts.pickup,1); eq(counts.turn_in,1); eq(counts.finish,1); eq(counts.later,1)
  eq(counts.chain,1); eq(counts.unknown,1); eq(counts.locked,1)
  eq(rows[1].id,2)
  R:Start("cleanup",12); assert(contains(R.plan,1)); assert(contains(R.plan,2))
end)
test("cleanup preserves skips exclusions and completion evidence",function()
  setup({[1]=q(1,{starters=endpoint(12)}),[2]=q(2,{category="dungeon",starters=endpoint(12)}),[3]=q(3)})
  scan(); R:Skip(1); A.modules.Selection:SetCategory("dungeon","exclude"); api.completed[3]=true; scan()
  local rows,counts=A.modules.Planning:Checklist(12)
  eq(#rows,2); eq(counts.preferences,2)
  R:Start("cleanup",12); eq(#R.plan,0); eq(next(A.charDB.completedEvidence),nil)
  local saved=A:Copy(A.charDB); setup({[1]=q(1)},saved); eq(A.charDB.journey.mode,"cleanup"); eq(A.charDB.journey.zoneID,12)
end)
test("forecast shows skipped and excluded cutoffs but omits completed and lost quests",function()
  setup({[1]=q(1,{maximumLevel=20}),[2]=q(2,{maximumLevel=21,category="dungeon"}),
    [3]=q(3,{maximumLevel=19}),[4]=q(4,{maximumLevel=30}),[5]=q(5,{maximumLevel=20,requiredClasses=128})})
  api.completed[4]=true; scan(); R:Skip(1); A.modules.Selection:SetCategory("dungeon","exclude")
  local p=A.modules.Planning
  eq(#p.forecast,2); eq(p.risks[1].priority,1); eq(p.risks[2].priority,1)
  assert(table.concat(p.risks[1].reasons):find("unavailable at level 21",1,true))
end)
test("held quests do not retain acquisition-level forecasts",function()
  setup({[1]=q(1,{maximumLevel=20})}); api.active={{questID=1}}; api.level=21; scan()
  eq(A.modules.Planning.risks[1],nil); eq(E:GetState(1),"active")
end)
test("forecast warns about parent turn-ins reputation skill and spell gates",function()
  setup({[1]=q(1),[2]=q(2,{parentQuest=1}),[3]=q(3,{requiredMaxRep={47,3000},requiredRanks={{762,-150}},requiredSpell=-123})})
  api.active={{questID=1},{questID=2}}; scan()
  local p=A.modules.Planning
  eq(p.risks[2].priority,1); eq(#p.risks[3].reasons,3)
end)
test("forecast consequence traversal preserves any-of alternatives and completed work",function()
  setup({[1]=q(1,{maximumLevel=20}),[2]=q(2,{prerequisitesAll={1}}),[3]=q(3,{prerequisitesAll={2}}),
    [4]=q(4),[5]=q(5,{prerequisitesAny={1,4}}),[6]=q(6,{prerequisitesAll={1}})})
  api.completed[6]=true; scan()
  local rows=A.modules.Planning:Consequences(1)
  eq(#rows,2); eq(rows[1].id,2); eq(rows[2].id,3)
end)
local function travelAPIs()
  api.now,api.bind,api.subzone,api.itemCount,api.cooldown=100,"Inn","Inn",1,0
  GetTime=function() return api.now end
  GetBindLocation=function() return api.bind end
  GetSubZoneText=function() return api.subzone end
  GetItemCount=function() return api.itemCount end
  GetItemCooldown=function() return api.cooldown,60,1 end
end
test("hearth mapping remains stable and invalidates when the bind changes",function()
  setup({}); travelAPIs(); scan(); local t=A.modules.Travel
  local saved=A:Copy(A.charDB.travel.hearth.point)
  C_Map.GetPlayerMapPosition=function() return {GetXY=function() return .8,.8 end} end
  t:ObserveBind(false); eq(A.charDB.travel.hearth.point.x,saved.x)
  api.bind="Other inn"; t:ObserveBind(false); eq(A.charDB.travel.hearth,nil); eq(t:Hearth(),nil)
  t:ObserveBind(true); eq(A.charDB.travel.hearth.name,"Other inn"); eq(A.charDB.travel.hearth.point.x,80)
end)
test("hearth routes require a carried item known cooldown and located bind",function()
  setup({}); travelAPIs(); scan(); local t=A.modules.Travel
  A.charDB.travel.hearth.point.areaId=40
  t:Prepare(); eq(t:Route({areaId=40,x=50,y=50}).kind,"hearth")
  api.cooldown=90; t:Prepare(); eq(t:Route({areaId=40,x=50,y=50}),nil); eq(t.hearthRemaining,50)
  local n=#timers; t:Prepare(); eq(#timers,n,"Do not schedule duplicate cooldown timers")
  api.now=151; t:Prepare(); assert(t:Route({areaId=40,x=50,y=50}))
  api.itemCount=0; t:Prepare(); eq(t:Route({areaId=40,x=50,y=50}),nil)
  api.itemCount=1; GetItemCooldown=nil; t:Prepare(); eq(t:Route({areaId=40,x=50,y=50}),nil)
end)
test("taxi observation stores only current and reachable nodes and directed edges",function()
  setup({}); scan(); local t=A.modules.Travel
  NumTaxiNodes=function() return 3 end; GetTaxiMapID=function() return 900 end
  TaxiNodeName=function(i) return ({"Start","End","Unknown"})[i] end
  TaxiNodeGetType=function(i) return ({"CURRENT","REACHABLE","DISTANT"})[i] end
  t:ObserveTaxi(); local m=A.charDB.travel
  assert(m.nodes["900:Start"].point); eq(m.nodes["900:End"].point,nil); eq(m.nodes["900:Unknown"],nil)
  eq(m.edges["900:Start"]["900:End"],true); eq(m.edges["900:End"],nil)
  m.nodes["900:End"].point={areaId=40,x=50,y=50}; t:Prepare()
  local route=t:Route({areaId=40,x=55,y=50}); assert(route.text:find("fly to End",1,true))
  eq(t:Route({areaId=85,x=50,y=50}),nil)
  TaxiNodeGetType=function(i) return i==1 and "CURRENT" or "DISTANT" end
  t:ObserveTaxi(); t:Prepare(); eq(t:Route({areaId=40,x=50,y=50}),nil)
end)
test("travel memory validates malformed saved points and connections",function()
  setup({}, {travel={nodes={bad=true,a={name="A",point={areaId=12,x=0/0,y=2}},b={name="B",point={areaId=40,x=50,y=50}}},
    edges={a={b=true,missing=true},b="bad"},hearth={name="Inn",point={areaId=0,x=1,y=1}}}})
  local m=A.charDB.travel; eq(m.nodes.bad,nil); eq(m.nodes.a.point,nil); eq(m.edges.a.b,true)
  eq(m.edges.a.missing,nil); eq(m.edges.b,nil); eq(m.hearth,nil)
  local saved=A:Copy(A.charDB); setup({},saved); eq(A.charDB.travel.nodes.b.point.areaId,40)
end)
test("manual transport observations survive reload and never infer reverse travel",function()
  setup({}); travelAPIs(); scan(); local t=A.modules.Travel
  assert(t:RecordDeparture("boat")); eq(t:RecordArrival(),false)
  local saved=A:Copy(A.charDB); setup({},saved); scan(); t=A.modules.Travel
  eq(A.charDB.travel.pending.kind,"boat")
  local original=t.Position
  t.Position=function() return {areaId=40,x=50,y=50} end
  assert(t:RecordArrival()); eq(A.charDB.travel.pending,nil)
  t.Position=original; t:Prepare()
  local route=t:Route({areaId=40,x=50,y=50}); assert(route.text:find("boat/zeppelin",1,true))
  t.Position=function() return {areaId=40,x=50,y=50} end; t:Prepare()
  eq(t:Route({areaId=12,x=50,y=50}),nil)
end)
test("observed transport accessibility influences fresh journey ordering",function()
  setup({[1]=q(1,{canonicalZone=40,starters=endpoint(40)}),[2]=q(2,{canonicalZone=85,starters=endpoint(85)})})
  local m=A.charDB.travel
  m.nodes.a={name="Start",point={areaId=12,x=50,y=50}}; m.nodes.b={name="End",point={areaId=85,x=50,y=50}}
  m.edges.a={b=true}; scan(); eq(R.plan[1].questID,2)
  assert(R.plan[1].travel.text:find("fly to End",1,true))
end)
test("riding rank changes local effort without inventing a flight connection",function()
  setup({}); scan(); local t=A.modules.Travel
  local walk=t:Route({areaId=12,x=80,y=50}).cost
  imports.QuestieProfessions.GetPlayerProfessions=function() return {[762]={"Riding",300}} end
  scan(); assert(t:Route({areaId=12,x=80,y=50}).cost<walk)
  eq(t:Route({areaId=40,x=80,y=50}),nil)
end)
test("planner UI handles pre-scan empty filtered and selected states",function()
  setup({[1]=q(1,{maximumLevel=20,starters=endpoint(12)}),[2]=q(2,{requiredLevel=60})})
  local ui=A.modules.UI; ui:Initialize(); ui:OpenPlanner("checklist"); assert(ui.planner:IsShown())
  scan(); ui:OpenPlanner("checklist",12); assert(ui.plannerSummary.value:find("1 pickups",1,true))
  ui.plannerRows[1].scripts.OnClick(); eq(ui.plannerQuest,1); eq(ui.plannerGuide.enabled,true)
  ui.plannerCleanup.scripts.OnClick(); eq(A.charDB.journey.mode,"cleanup")
  ui:OpenPlanner("forecast"); ui.plannerRows[1].scripts.OnClick()
  assert(ui.plannerDetails.value:find("unavailable at level 21",1,true))
  R:Skip(1); ui:_RefreshPlanner(); eq(ui.plannerGuide.enabled,false)
  ui.plannerSearch:SetText("no match"); ui:_RefreshPlanner(); eq(ui.plannerQuest,nil); eq(ui.plannerInspect.enabled,false)
  ui:OpenPlanner("travel"); assert(ui.transportDeparture:IsShown()); eq(ui.transportArrival.enabled,false)
  assert(ui.plannerDetails.value:find("remembered stops",1,true)); eq(#errors,0)
end)

for _,case in ipairs(cases) do
  local ok,message=pcall(case[2])
  if not ok then io.stderr:write("FAIL: "..case[1].."\n"..tostring(message).."\n"); os.exit(1) end
  passed=passed+1
end
print("PASS: "..passed.." Lua runtime behavior tests")
