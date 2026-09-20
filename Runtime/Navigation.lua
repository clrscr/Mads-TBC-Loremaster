local Addon=MadsTBC
local Navigation={}
Addon:RegisterModule("Navigation",Navigation)
function Navigation:Initialize() self.current,self.tomtomUID,self.key=nil,nil,nil end
function Navigation:_UiMapID(areaID)
  local db=Addon:Import("ZoneDB")
  if db and db.GetUiMapIdByAreaId then
    local ok,map=pcall(db.GetUiMapIdByAreaId,db,areaID)
    if ok and Addon:IsID(map) then return map end
  end
end
function Navigation:PlayerPosition()
  local c=Addon.modules.Character.snapshot
  local position=C_Map and c.uiMapID and C_Map.GetPlayerMapPosition and C_Map.GetPlayerMapPosition(c.uiMapID,"player")
  if position and position.GetXY then return {position:GetXY()} end
  return {}
end
function Navigation:_PointForAction(action, playerPosition)
  if not action then return nil end
  local q=Addon:GetQuest(action.questID)
  if not q then return nil end
  local sources
  if action.type=="accept" then sources=q.starters or (q.starter and {q.starter})
  elseif action.type=="turn_in" then sources=q.finishers or (q.finisher and {q.finisher})
  elseif action.type=="objective" then
    -- Match named targets or a single unambiguous objective. Flattened source
    -- order alone does not establish the client objective order or locale.
    local live=Addon.modules.Character:IsActive(q.id)
    local objective=live and live.objectives and live.objectives[action.objectiveIndex]
    local expected={monster="npc",object="object",item="item"}
    local kind=objective and expected[objective.type]
    if kind and action.objectiveIndex then
      local matches,candidates={},{}
      local title=type(objective.text)=="string" and string.lower(objective.text) or ""
      for _, source in ipairs(q.objectives or {}) do
        local name=type(source.name)=="string" and string.lower(source.name) or ""
        if source.kind==kind and name~="" and string.find(title,name,1,true) then
          table.insert(matches,{source=source,name=name})
        end
      end
      local matchedName,ambiguous
      for _,match in ipairs(matches) do
        local contained=false
        for _,other in ipairs(matches) do
          if other.name~=match.name and string.find(other.name,match.name,1,true) then contained=true; break end
        end
        -- A Hulking Mountain Lion objective must not select a nearer Mountain
        -- Lion. Distinct remaining names still leave the target ambiguous.
        if not contained then
          if matchedName and matchedName~=match.name then ambiguous=true end
          matchedName=match.name
          table.insert(candidates,match.source)
        end
      end
      if #candidates>0 and not ambiguous then sources=candidates
      elseif q.objectives and #q.objectives==1 and #live.objectives==1 and q.objectives[1].kind==kind then
        sources=q.objectives
      end
    end
    if not action.objectiveIndex and q.objectives and #q.objectives==1 then sources=q.objectives end
  end
  local selected,best,owner
  local c=Addon.modules.Character.snapshot
  local position=playerPosition or self:PlayerPosition()
  local px,py=position[1],position[2]
  for _, source in ipairs(sources or {}) do
    for _, p in ipairs(source.points or (source.point and {source.point}) or {}) do
      if Addon:IsID(p.areaId) and Addon:IsNumber(p.x) and Addon:IsNumber(p.y) and p.x>=0 and p.x<=100 and p.y>=0 and p.y<=100 then
        local distance=p.areaId==c.currentAreaID and 0 or 100000
        if distance==0 and px and py then distance=(p.x-px*100)^2+(p.y-py*100)^2 end
        if not best or distance<best then selected,best,owner=p,distance,source end
      end
    end
  end
  return selected,owner,best
end
function Navigation:SetForAction(action)
  self.travel=action and action.travel
  local point,source=self:_PointForAction(action)
  if self.travel and self.travel.waypoint then point,source=self.travel.waypoint,nil end
  local map=point and self:_UiMapID(point.areaId)
  local key=point and table.concat({action.key,point.areaId,point.x,point.y,map or "unknown",tostring(TomTom)},":") or nil
  self.current=point
  if key==self.key then return end
  self.key=key
  if self.tomtomUID and TomTom and TomTom.RemoveWaypoint then pcall(TomTom.RemoveWaypoint,TomTom,self.tomtomUID) end
  self.tomtomUID=nil
  if not point or not map then return end
  if TomTom and TomTom.AddWaypoint then
    local q=Addon:GetQuest(action.questID)
    local ok,uid=pcall(TomTom.AddWaypoint,TomTom,map,point.x/100,point.y/100,
      {title=q.name..(source and source.name and " — "..source.name or ""),persistent=false,minimap=true,world=true,crazy=true})
    if ok then self.tomtomUID=uid else self.key=nil end
  end
end
function Navigation:Description()
  if not self.current then return "No source-backed destination for this action. Consult the quest instructions." end
  return string.format("%s — %.1f, %.1f",self.current.mapName or "Map",self.current.x,self.current.y)
end

-- Transport hints use the pinned TBC NPC snapshot (3149, 3150, 9564,
-- 9566, 12136, 12137). A master location is evidence for a hub, not a
-- verified timetable or permission to board a particular service.
function Navigation:TravelHint()
  if self.travel then return self.travel.text end
  local c=Addon.modules.Character.snapshot
  if not self.current or not c.currentAreaID or self.current.areaId==c.currentAreaID then return nil end
  local destination=self.current.mapName or "the destination zone"
  local hint="Travel to "..destination..". Use a known flight path or a road/zone connection you can access."
  if c.faction=="Horde" then
    local hubs={[14]="the zeppelin masters north of Orgrimmar",[85]="the zeppelin masters outside Undercity",[33]="the zeppelin masters at Grom'gol"}
    if hubs[c.currentAreaID] then hint=hint.." For a continent crossing, check "..hubs[c.currentAreaID].." and confirm the destination before boarding." end
  end
  return hint
end
