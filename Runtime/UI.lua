local Addon = MadsTBC
local UI = {}
Addon:RegisterModule("UI", UI)

local GOLD = {0.84, 0.66, 0.29}
local PANEL = {0.055, 0.065, 0.085, 0.97}

local function makeText(parent, size, color, justify)
  local text = parent:CreateFontString(nil, "OVERLAY", size >= 16 and "GameFontNormalLarge" or "GameFontHighlight")
  text:SetTextColor(unpack(color or {0.9, 0.9, 0.9}))
  text:SetJustifyH(justify or "LEFT")
  text:SetJustifyV("TOP")
  return text
end

local function styleFrame(frame)
  if frame.SetBackdrop then
    frame:SetBackdrop({
      bgFile = "Interface/Tooltips/UI-Tooltip-Background",
      edgeFile = "Interface/Tooltips/UI-Tooltip-Border",
      tile = true, tileSize = 16, edgeSize = 14,
      insets = {left = 4, right = 4, top = 4, bottom = 4},
    })
    frame:SetBackdropColor(unpack(PANEL))
    frame:SetBackdropBorderColor(unpack(GOLD))
  end
end

local function contains(list, wanted)
  for _, value in ipairs(list or {}) do if value == wanted then return true end end
  return false
end

local function percentage(done, total)
  if not total or total == 0 then return 100 end
  return math.floor(done * 100 / total + 0.5)
end

function UI:Initialize()
  self.page = "overview"
  self.zonePage = 1
  self:_CreateDashboard()
  self:_CreateTracker()
  Addon:On("STATE_UPDATED", function() self:Refresh() end)
  if not Addon.charDB.firstScanComplete then self.dashboard:Show() end
end

function UI:_CreateDashboard()
  local template = BackdropTemplateMixin and "BackdropTemplate" or nil
  local frame = CreateFrame("Frame", "MadsTBCLoremasterDashboard", UIParent, template)
  frame:SetSize(720, 520)
  frame:SetPoint(Addon.db.window.point, UIParent, Addon.db.window.point, Addon.db.window.x, Addon.db.window.y)
  frame:SetMovable(true)
  frame:EnableMouse(true)
  frame:RegisterForDrag("LeftButton")
  frame:SetScript("OnDragStart", frame.StartMoving)
  frame:SetScript("OnDragStop", function(self)
    self:StopMovingOrSizing()
    local point, _, _, x, y = self:GetPoint()
    Addon.db.window = {point = point, x = x, y = y}
  end)
  frame:SetFrameStrata("DIALOG")
  frame:Hide()
  styleFrame(frame)
  self.dashboard = frame

  local title = makeText(frame, 20, GOLD)
  title:SetPoint("TOPLEFT", 22, -18)
  title:SetText("Mad's TBC Loremaster")
  local subtitle = makeText(frame, 12, {0.65, 0.7, 0.78})
  subtitle:SetPoint("TOPLEFT", title, "BOTTOMLEFT", 0, -3)
  subtitle:SetText("Alliance completion, catch-up, and story routing — powered by Questie")

  local close = CreateFrame("Button", nil, frame, "UIPanelCloseButton")
  close:SetPoint("TOPRIGHT", -6, -6)

  self.tabs = {}
  for index, page in ipairs({"overview", "zones", "recurring", "settings"}) do
    local button = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    button:SetSize(105, 24)
    button:SetPoint("TOPLEFT", 20 + (index - 1) * 110, -62)
    button:SetText(page:gsub("^%l", string.upper))
    button:SetScript("OnClick", function() self:SetPage(page) end)
    self.tabs[page] = button
  end

  self.summaryTitle = makeText(frame, 18, {0.95, 0.95, 0.95})
  self.summaryTitle:SetPoint("TOPLEFT", 24, -104)
  self.summaryTitle:SetWidth(670)
  self.summaryTitle:SetText("Scanning character…")
  self.summaryBody = makeText(frame, 13, {0.76, 0.8, 0.86})
  self.summaryBody:SetPoint("TOPLEFT", self.summaryTitle, "BOTTOMLEFT", 0, -10)
  self.summaryBody:SetWidth(670)
  self.summaryBody:SetHeight(75)

  self.modeButtons = {}
  local modes = {
    {"continue", "Continue Journey"},
    {"catchup", "Catch Up on What You Missed"},
    {"back_on_track", "Get Back on Track"},
  }
  for index, row in ipairs(modes) do
    local button = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    button:SetSize(210, 32)
    button:SetPoint("TOPLEFT", 24 + (index - 1) * 224, -205)
    button:SetText(row[2])
    button:SetScript("OnClick", function() Addon.modules.Router:Start(row[1]) end)
    self.modeButtons[index] = button
  end

  self.zoneHeader = makeText(frame, 15, GOLD)
  self.zoneHeader:SetPoint("TOPLEFT", 24, -258)
  self.zoneHeader:SetText("Zone completion")
  self.zoneRows = {}
  for index = 1, 8 do
    local row = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    row:SetSize(650, 25)
    row:SetPoint("TOPLEFT", 24, -282 - (index - 1) * 27)
    row:GetFontString():SetJustifyH("LEFT")
    self.zoneRows[index] = row
  end
  self.previousZones = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  self.previousZones:SetSize(80, 23)
  self.previousZones:SetPoint("BOTTOMLEFT", 24, 18)
  self.previousZones:SetText("Previous")
  self.previousZones:SetScript("OnClick", function()
    self.zonePage = math.max(1, self.zonePage - 1)
    self:Refresh()
  end)
  self.nextZones = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  self.nextZones:SetSize(80, 23)
  self.nextZones:SetPoint("BOTTOMRIGHT", -24, 18)
  self.nextZones:SetText("Next")
  self.nextZones:SetScript("OnClick", function()
    self.zonePage = self.zonePage + 1
    self:Refresh()
  end)

  self.detailButton = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  self.detailButton:SetSize(190, 30)
  self.detailButton:SetPoint("TOPLEFT", 24, -220)
  self.detailButton:SetScript("OnClick", function()
    local order = {minimal = "route", route = "arc", arc = "deep", deep = "minimal"}
    Addon:SetDetailLevel(order[Addon.db.detailLevel] or "minimal")
  end)
  self.rescanButton = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  self.rescanButton:SetSize(130, 30)
  self.rescanButton:SetPoint("LEFT", self.detailButton, "RIGHT", 12, 0)
  self.rescanButton:SetText("Rescan Character")
  self.rescanButton:SetScript("OnClick", function() Addon:Rescan("manual") end)
  self.phaseButton = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  self.phaseButton:SetSize(190, 30)
  self.phaseButton:SetPoint("TOPLEFT", self.detailButton, "BOTTOMLEFT", 0, -12)
  self.phaseButton:SetScript("OnClick", function()
    local current = Addon.db.phaseOverride
    if current == nil then current = Addon.Manifest.phase.number
    else current = current + 1 end
    if current > 5 then current = nil end
    Addon:SetPhaseOverride(current)
  end)
  self.restoreButton = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  self.restoreButton:SetSize(190, 30)
  self.restoreButton:SetPoint("TOPLEFT", self.phaseButton, "BOTTOMLEFT", 0, -12)
  self.restoreButton:SetScript("OnClick", function()
    Addon.charDB.deferred = {}
    Addon:Rescan("restore_deferred")
  end)
end

function UI:_CreateTracker()
  local template = BackdropTemplateMixin and "BackdropTemplate" or nil
  local frame = CreateFrame("Frame", "MadsTBCLoremasterTracker", UIParent, template)
  frame:SetSize(360, 150)
  frame:SetPoint("RIGHT", UIParent, "RIGHT", -45, 40)
  frame:SetMovable(true)
  frame:EnableMouse(true)
  frame:RegisterForDrag("LeftButton")
  frame:SetScript("OnDragStart", frame.StartMoving)
  frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
  styleFrame(frame)
  self.tracker = frame

  self.trackerMode = makeText(frame, 12, GOLD)
  self.trackerMode:SetPoint("TOPLEFT", 14, -12)
  self.trackerMode:SetWidth(325)
  self.trackerStep = makeText(frame, 14, {0.95, 0.95, 0.95})
  self.trackerStep:SetPoint("TOPLEFT", self.trackerMode, "BOTTOMLEFT", 0, -8)
  self.trackerStep:SetWidth(330)
  self.trackerStep:SetHeight(38)
  self.trackerMeta = makeText(frame, 11, {0.67, 0.72, 0.8})
  self.trackerMeta:SetPoint("TOPLEFT", self.trackerStep, "BOTTOMLEFT", 0, -5)
  self.trackerMeta:SetWidth(330)
  self.trackerMeta:SetHeight(34)
  local open = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  open:SetSize(100, 22)
  open:SetPoint("BOTTOMLEFT", 14, 11)
  open:SetText("Dashboard")
  open:SetScript("OnClick", function() self.dashboard:Show() end)
  self.defer = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  self.defer:SetSize(85, 22)
  self.defer:SetPoint("LEFT", open, "RIGHT", 8, 0)
  self.defer:SetText("Defer")
  self.defer:SetScript("OnClick", function() Addon.modules.Router:DeferCurrent() end)
end

function UI:SetPage(page)
  self.page = page
  self.zonePage = 1
  self:Refresh()
end

function UI:Toggle()
  if self.dashboard:IsShown() then self.dashboard:Hide() else self.dashboard:Show() end
end

function UI:_SortedZones(page)
  local result = {}
  for _, zone in pairs(Addon.modules.Eligibility.zones or {}) do
    local visible = page == "recurring" and zone.recurring > 0
      or page == "overview" and zone.geographic and zone.actionable > 0
      or page == "zones" and zone.geographic and zone.total > 0
    if visible then
      table.insert(result, zone)
    end
  end
  table.sort(result, function(a, b)
    local ap, bp = percentage(a.completed, a.total), percentage(b.completed, b.total)
    if ap ~= bp then return ap < bp end
    return a.name < b.name
  end)
  return result
end

function UI:_RefreshDashboard()
  local summary = Addon.modules.Eligibility.summary or {}
  local character = Addon.modules.Character.snapshot or {}
  local supported = character.faction == "Alliance"
  for _, button in ipairs(self.modeButtons) do
    if supported then button:Enable() else button:Disable() end
  end
  local done, total = summary.permanentCompleted or 0, summary.permanentTotal or 0
  if not supported and character.faction then
    self.summaryTitle:SetText("Alliance characters are supported in v1")
    self.summaryBody:SetText("This character is " .. tostring(character.faction) .. ". Quest records remain visible for audit purposes, but completion scoring and route generation are disabled.")
  else
  self.summaryTitle:SetText(string.format("Permanent completion: %d / %d  (%d%%)", done, total, percentage(done, total)))
  local firstLaunch = not Addon.charDB.firstScanComplete and "Choose how you want to begin. " or ""
  self.summaryBody:SetText(string.format(
    "%s%d available now · %d prerequisite or level blockers · %d locked · %d unselected alternatives\nRecurring activity: %d / %d this cycle · %d completed at least once",
    firstLaunch, summary.available or 0, summary.blocked or 0, summary.locked or 0, summary.alternatives or 0,
    summary.recurringCurrent or 0, summary.recurringAvailable or 0, summary.recurringLifetime or 0
  ))
  end
  local overview = self.page == "overview"
  local settings = self.page == "settings"
  for _, button in ipairs(self.modeButtons) do if overview then button:Show() else button:Hide() end end
  self.zoneHeader:SetShown(not settings)
  self.detailButton:SetShown(settings)
  self.rescanButton:SetShown(settings)
  self.phaseButton:SetShown(settings)
  self.restoreButton:SetShown(settings)
  if settings then
    self.summaryTitle:SetText("Settings and disclosure")
    self.summaryBody:SetText("Quest actions stay concise by default. Cycle through Route, Arc, and Deep Lore when you want more context. Completion data can be rescanned at any time.")
    self.detailButton:SetText("Detail: " .. (Addon.db.detailLevel or "minimal"))
    self.phaseButton:SetText(
      Addon.db.phaseOverride and ("Phase override: " .. Addon.db.phaseOverride)
      or ("Phase: Automatic (" .. Addon.Manifest.phase.number .. ")")
    )
    local deferred = 0
    for _ in pairs(Addon.charDB.deferred or {}) do deferred = deferred + 1 end
    self.restoreButton:SetText("Restore Deferred (" .. deferred .. ")")
  elseif self.page == "recurring" then
    self.summaryTitle:SetText("Recurring and event activity")
    self.summaryBody:SetText(string.format(
      "%d of %d currently available recurring quests complete · %d recurring quests completed at least once. These never change the permanent completion score.",
      summary.recurringCurrent or 0, summary.recurringAvailable or 0, summary.recurringLifetime or 0
    ))
    self.zoneHeader:SetText("Recurring activity by canonical zone")
  elseif self.page == "zones" then
    self.zoneHeader:SetText("Select a zone to build a completion sweep")
  else
    self.zoneHeader:SetText("Zones needing attention")
  end

  local zones = settings and {} or self:_SortedZones(self.page)
  local start = (self.zonePage - 1) * #self.zoneRows + 1
  for index, row in ipairs(self.zoneRows) do
    local zone = zones[start + index - 1]
    if zone then
      local suffix
      if self.page == "recurring" then
        suffix = string.format("%d recurring", zone.recurring)
      else
        suffix = string.format("%d/%d · %d%% · %d available · %d blocked", zone.completed, zone.total, percentage(zone.completed, zone.total), zone.available, zone.blocked)
      end
      row:SetText("  " .. zone.name .. "    " .. suffix)
      row:SetScript("OnClick", function() Addon.modules.Router:Start("zone", zone.id) end)
      if supported then row:Enable() else row:Disable() end
      row:Show()
    else
      row:Hide()
    end
  end
  self.previousZones:SetShown(not settings and self.zonePage > 1)
  self.nextZones:SetShown(not settings and start + #self.zoneRows - 1 < #zones)
end

function UI:_RefreshTracker()
  local quest, state, index, total = Addon.modules.Router:GetCurrent()
  if not quest then
    self.trackerMode:SetText("No route selected")
    self.trackerStep:SetText("Open the dashboard to Continue, Catch Up, or Get Back on Track.")
    self.trackerMeta:SetText("Your completed-quest scan remains available in the dashboard.")
    self.defer:Hide()
    return
  end
  self.trackerMode:SetText(string.format("%s · step %d of %d · %s", Addon.modules.Router:ModeLabel(), index, total, quest.zoneName))
  self.trackerStep:SetText(Addon.modules.Router:DescribeStep(quest, state))
  local detail = Addon:GetLore(quest.canonicalZone, Addon.db.detailLevel)
  local navigation = Addon.modules.Navigation:Description()
  self.trackerMeta:SetText(detail and (navigation .. "\n" .. detail) or navigation)
  self.defer:SetShown(contains(quest.kinds, "group_content") or quest.category == "pvp")
end

function UI:Refresh()
  if not self.dashboard then return end
  self:_RefreshDashboard()
  self:_RefreshTracker()
end

StaticPopupDialogs.MADS_TBC_LOREMASTER_CHOICE = {
  text = "%s conflicts with another quest outcome. Mad's TBC Loremaster will preserve the completed outcome and remove locked alternatives from your achievable-completion score.\n\nConflicts: %s",
  button1 = OKAY,
  timeout = 0,
  whileDead = true,
  hideOnEscape = true,
  preferredIndex = 3,
  OnAccept = function(_, data)
    if data then Addon.charDB.acknowledgedChoices[data] = true end
  end,
}

function UI:MaybeWarnChoice(questID)
  if Addon.charDB.acknowledgedChoices[questID] then return end
  local quest = Addon.Manifest.quests[questID]
  if not quest or not quest.exclusiveTo or #quest.exclusiveTo == 0 then return end
  local names = {}
  local recommended = quest
  for _, otherID in ipairs(quest.exclusiveTo) do
    local other = Addon.Manifest.quests[otherID]
    if other then
      table.insert(names, other.name)
      if other.routeOrder and (not recommended.routeOrder or other.routeOrder < recommended.routeOrder) then
        recommended = other
      end
    end
    if #names == 3 then break end
  end
  if #names > 0 then
    local detail = table.concat(names, ", ") .. "\n\nRecommended route outcome: " .. recommended.name
    StaticPopup_Show("MADS_TBC_LOREMASTER_CHOICE", quest.name, detail, questID)
  end
end
