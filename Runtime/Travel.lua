local Addon=MadsTBC
local Travel={}
Addon:RegisterModule("Travel",Travel)
local connections={boat=true,portal=true,road=true}
local function call(fn,...)
  if type(fn)~="function" then return nil end
  local ok,a,b,c=pcall(fn,...)
  if ok then return a,b,c end
end
local function validPoint(p)
  return type(p)=="table" and Addon:IsID(p.areaId) and Addon:IsNumber(p.x) and Addon:IsNumber(p.y)
    and p.x>=0 and p.x<=100 and p.y>=0 and p.y<=100
end
function Travel:Normalize(value)
  value=type(value)=="table" and value or {}
  local result={nodes={},edges={}}
  for key,node in pairs(type(value.nodes)=="table" and value.nodes or {}) do
    if type(key)=="string" and #key<300 and type(node)=="table" and type(node.name)=="string" then
      result.nodes[key]={name=string.sub(node.name,1,200),point=validPoint(node.point) and Addon:Copy(node.point) or nil}
    end
  end
  for from,edges in pairs(type(value.edges)=="table" and value.edges or {}) do
    if result.nodes[from] and type(edges)=="table" then
      result.edges[from]={}
      for to,known in pairs(edges) do
        if result.nodes[to] and (known==true or connections[known]) then result.edges[from][to]=known end
      end
    end
  end
  local hearth=value.hearth
  if type(hearth)=="table" and type(hearth.name)=="string" and validPoint(hearth.point) then
    result.hearth={name=string.sub(hearth.name,1,200),point=Addon:Copy(hearth.point)}
  end
  local pending=value.pending
  if type(pending)=="table" and connections[pending.kind] and validPoint(pending.point) and type(pending.name)=="string" then
    result.pending={kind=pending.kind,point=Addon:Copy(pending.point),name=string.sub(pending.name,1,200)}
  end
  return result
end
function Travel:Initialize() self.routes={}; self.cooldownToken=0 end
function Travel:Position()
  local map=call(C_Map and C_Map.GetBestMapForUnit,"player")
  local db=Addon:Import("ZoneDB")
  local area=db and call(db.GetAreaIdByUiMapId,db,map)
  local pos=map and call(C_Map and C_Map.GetPlayerMapPosition,map,"player")
  local x,y
  if pos and pos.GetXY then x,y=call(pos.GetXY,pos) end
  local p={areaId=area,x=x and x*100,y=y and y*100}
  return validPoint(p) and p or nil
end
function Travel:ObserveBind(bound)
  local memory=Addon.charDB.travel
  local name=call(GetBindLocation)
  if type(name)~="string" or name=="" then return end
  if memory.hearth and memory.hearth.name~=name then memory.hearth=nil end
  -- Exact localized zone/subzone match can locate an existing bind. A bind
  -- event establishes the new inn location even when its name differs.
  if bound or (not memory.hearth and name==call(GetSubZoneText)) then
    local p=self:Position()
    if p then memory.hearth={name=name,point=p} end
  end
end
function Travel:Hearth()
  local memory=Addon.charDB.travel.hearth
  local name=call(GetBindLocation)
  if not memory or memory.name~=name then return nil,"Hearth location not mapped yet; visit your bound inn or bind at an inn." end
  local count=call(C_Item and C_Item.GetItemCount or GetItemCount,6948,false,false)
  if not Addon:IsNumber(count) or count<1 then return nil,"No carried Hearthstone detected." end
  local fn=C_Container and C_Container.GetItemCooldown or GetItemCooldown
  local start,duration,enabled=call(fn,6948)
  local now=call(GetTime)
  if not Addon:IsNumber(start) or not Addon:IsNumber(duration) or not Addon:IsNumber(now) or enabled~=1 then
    return nil,"Hearthstone cooldown is unavailable."
  end
  local remaining=math.max(0,start+duration-now)
  if remaining>0 then return nil,"Hearth to "..memory.name.." in "..math.ceil(remaining/60).." min.",remaining end
  return memory,"Hearth ready: "..memory.name.."."
end
function Travel:ObserveTaxi()
  local count,map=call(NumTaxiNodes),call(GetTaxiMapID)
  if not Addon:IsID(count) or count>1000 or not Addon:IsID(map) then return end
  local nodes,reachable,current={},{}
  for i=1,count do
    local kind,name=call(TaxiNodeGetType,i),call(TaxiNodeName,i)
    if (kind=="CURRENT" or kind=="REACHABLE") and type(name)=="string" and name~="" then
      local key=map..":"..name
      nodes[key]={name=name}
      if kind=="CURRENT" then current=key else reachable[key]=true end
    end
  end
  if not current then return end
  local memory=Addon.charDB.travel
  for key,node in pairs(nodes) do memory.nodes[key]=memory.nodes[key] or node end
  local point=self:Position()
  if point then memory.nodes[current].point=point end
  -- Reachable means a verified directed connection, including intermediate
  -- stops. Never infer the reverse edge or discover DISTANT nodes.
  memory.edges[current]=reachable
end
function Travel:RecordDeparture(kind)
  if not connections[kind] then return end
  local point=self:Position()
  if not point then return false,"Your map position is unavailable." end
  Addon.charDB.travel.pending={kind=kind,point=point,name=call(GetSubZoneText) or call(GetZoneText) or ("Area "..point.areaId)}
  return true,"Departure saved. Use the connection, then record arrival to confirm its direction."
end
function Travel:RecordArrival()
  local memory=Addon.charDB.travel
  local pending,point=memory.pending,self:Position()
  if not pending then return false,"Record a departure first." end
  if not point then return false,"Your arrival map position is unavailable." end
  if point.areaId==pending.point.areaId and math.abs(point.x-pending.point.x)+math.abs(point.y-pending.point.y)<1 then
    return false,"You are still at the recorded departure. Record arrival after traveling."
  end
  local function key(p) return string.format("transport:%d:%.1f:%.1f",p.areaId,p.x,p.y) end
  local from,to=key(pending.point),key(point)
  memory.nodes[from]={name=pending.name,point=pending.point}
  memory.nodes[to]={name=call(GetSubZoneText) or call(GetZoneText) or ("Area "..point.areaId),point=point}
  memory.edges[from]=memory.edges[from] or {}; memory.edges[from][to]=pending.kind
  memory.pending=nil
  return true,"Connection saved in the direction you traveled. Record the return trip separately if needed."
end
local function distance(a,b)
  if not a or not b or a.areaId~=b.areaId then return nil end
  return math.sqrt((a.x-b.x)^2+(a.y-b.y)^2)
end
function Travel:Prepare()
  self:ObserveBind(false)
  self.position=self:Position()
  local c=Addon.modules.Character.snapshot
  self.riding=c.professions and c.professions[762] or 0
  -- Relative effort only: coordinates have different scales between maps.
  -- Riding lowers local ground effort but never establishes flight access.
  self.groundFactor=self.riding>=150 and .5 or self.riding>=75 and .625 or 1
  self.hearth,self.hearthStatus,self.hearthRemaining=self:Hearth()
  self.routes={}
  local memory=Addon.charDB.travel
  local costs,paths,waypoints,visited={},{},{},{}
  for key,node in pairs(memory.nodes) do
    local d=distance(self.position,node.point)
    if d then costs[key]=d*self.groundFactor; paths[key]="Travel to "..node.name; waypoints[key]=node.point end
    local h=self.hearth and distance(self.hearth.point,node.point)
    if h and (not costs[key] or 15+h*self.groundFactor<costs[key]) then
      costs[key]=15+h*self.groundFactor; paths[key]="Hearth to "..self.hearth.name..", then travel to "..node.name
      waypoints[key]=self.hearth.point
    end
  end
  -- Dijkstra over observed flight links and same-zone ground transfers.
  while true do
    local best
    for key,cost in pairs(costs) do
      if not visited[key] and (not best or cost<costs[best] or cost==costs[best] and key<best) then best=key end
    end
    if not best then break end
    visited[best]=true
    local source=memory.nodes[best]
    for key,node in pairs(memory.nodes) do
      if not visited[key] then
        local ground=distance(source.point,node.point)
        local connection=memory.edges[best] and memory.edges[best][key]
        local cost=connection==true and 20 or connection=="portal" and 10 or connection=="boat" and 30
          or connection=="road" and 80*self.groundFactor or ground and ground*self.groundFactor
        if cost and (not costs[key] or costs[best]+cost<costs[key]) then
          costs[key]=costs[best]+cost
          local verb=connection==true and "; fly to " or connection=="boat" and "; take the recorded boat/zeppelin to "
            or connection=="portal" and "; take the recorded portal to " or "; travel to "
          paths[key]=paths[best]..verb..node.name
          waypoints[key]=waypoints[best]
        end
      end
    end
  end
  self.costs,self.paths,self.waypoints=costs,paths,waypoints
  -- Reconsider routing at cooldown expiry without polling each frame.
  local deadline=self.hearthRemaining and (call(GetTime) or 0)+self.hearthRemaining
  if deadline and (not self.cooldownDeadline or math.abs(deadline-self.cooldownDeadline)>1) then
    self.cooldownDeadline=deadline; self.cooldownToken=self.cooldownToken+1
    local token=self.cooldownToken
    C_Timer.After(self.hearthRemaining+.2,function()
      if token~=self.cooldownToken then return end
      self.cooldownDeadline=nil
      Addon:Rescan("hearth_ready")
    end)
  end
end
function Travel:Route(point)
  if not validPoint(point) then return nil end
  local key=table.concat({point.areaId,point.x,point.y},":")
  if self.routes[key]~=nil then return self.routes[key] or nil end
  local best
  local d=distance(self.position,point)
  if d then best={cost=d*self.groundFactor,text="Continue locally"..(self.riding>=75 and "; use your ground mount where possible." or "."),kind="ground"} end
  local function candidate(cost,text,kind,waypoint)
    if not best or cost<best.cost then best={cost=cost,text=text,kind=kind,waypoint=waypoint} end
  end
  local h=self.hearth and distance(self.hearth.point,point)
  if h then candidate(15+h*self.groundFactor,"Hearth to "..self.hearth.name..", then continue to the quest destination.","hearth",self.hearth.point) end
  for node,cost in pairs(self.costs or {}) do
    local finish=distance(Addon.charDB.travel.nodes[node].point,point)
    if finish then candidate(cost+finish*self.groundFactor,self.paths[node].."; continue to the quest destination.","connection",self.waypoints[node]) end
  end
  self.routes[key]=best or false
  return best
end
function Travel:Summary()
  local nodes,located,links=0,0,0
  for _,node in pairs(Addon.charDB.travel.nodes) do nodes=nodes+1; if node.point then located=located+1 end end
  for _,edges in pairs(Addon.charDB.travel.edges) do for _ in pairs(edges) do links=links+1 end end
  local _,hearth=self:Hearth()
  return string.format("%d remembered stops; %d located; %d observed connections.\n%s\nRiding rank: %s. Routes compare relative effort, not arrival times.\nOpen flight maps at visited masters to learn connections and locate endpoints. Flight riding does not imply a usable flying mount.\nRecord boat, portal, and road connections with the departure/arrival buttons. Unrecorded connections remain manual travel.",nodes,located,links,hearth,tostring(self.riding or 0))
end
