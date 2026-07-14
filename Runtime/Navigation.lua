local Addon = MadsTBC
local Navigation = {}
Addon:RegisterModule("Navigation", Navigation)

function Navigation:Initialize()
  self.current = nil
  self.tomtomUID = nil
end

function Navigation:_PointFor(questID)
  local quest = Addon.Manifest.quests[questID]
  if not quest then return nil end
  local state = Addon.modules.Eligibility:GetState(questID)
  local source = state == "ready_to_turn_in" and quest.finisher
    or state == "active" and quest.objective
    or quest.starter
  return source and source.point, source
end

function Navigation:_UiMapID(areaID)
  if QuestieLoader then
    local ok, zoneDB = pcall(function() return QuestieLoader:ImportModule("ZoneDB") end)
    if ok and zoneDB then
      if zoneDB.GetUiMapIdByAreaId then
        local mappedOK, mapped = pcall(zoneDB.GetUiMapIdByAreaId, zoneDB, areaID)
        if mappedOK and mapped and mapped > 0 then return mapped end
      elseif zoneDB.private and zoneDB.private.areaIdToUiMapId then
        local mapped = zoneDB.private.areaIdToUiMapId[areaID]
        if mapped and mapped > 0 then return mapped end
      end
    end
  end
  return areaID
end

function Navigation:SetForQuest(questID)
  local point, source = self:_PointFor(questID)
  self.current = point
  if self.tomtomUID and TomTom and TomTom.RemoveWaypoint then
    pcall(TomTom.RemoveWaypoint, TomTom, self.tomtomUID)
    self.tomtomUID = nil
  end
  if not point then return end
  local quest = Addon.Manifest.quests[questID]
  local uiMapID = self:_UiMapID(point.areaId)
  if TomTom and TomTom.AddWaypoint then
    local ok, uid = pcall(TomTom.AddWaypoint, TomTom, uiMapID, point.x / 100, point.y / 100, {
      title = quest.name .. (source and source.name and " — " .. source.name or ""),
      persistent = false,
      minimap = true,
      world = true,
      crazy = true,
    })
    if ok then self.tomtomUID = uid end
  end
end

function Navigation:Description()
  if not self.current then return "No verified waypoint for this step." end
  return string.format("%s — %.1f, %.1f", self.current.mapName or "Map", self.current.x, self.current.y)
end
