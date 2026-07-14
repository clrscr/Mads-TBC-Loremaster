MadsTBC = MadsTBC or {}

-- Original, spoiler-light summaries. Quest names and progress remain data-driven.
MadsTBC.Lore = {
  [141] = {
    arc = "Teldrassil introduces the kaldorei homeland, its strained balance, and the duties that draw a new adventurer beyond the great tree.",
    deep = "The starting stories connect the druids, Sentinels, and settlements of Teldrassil while foreshadowing the wider troubles along northern Kalimdor.",
  },
  [148] = {
    arc = "Darkshore follows the night elves rebuilding along a dangerous coast while corruption, shipwrecks, and old ruins threaten Auberdine.",
    deep = "Its chains move between local survival and the older history of the Highborne, linking the coast to Ashenvale and the wider Alliance journey.",
  },
  [331] = {
    arc = "Ashenvale is a contested forest where the night elves defend sacred ground against corruption and an expanding Horde presence.",
    deep = "The zone brings the Warsong conflict, the Sentinels, ancient spirits, and demonic remnants into one of Kalimdor's central Alliance storylines.",
  },
  [12] = {
    arc = "Elwynn Forest grounds the human story in local threats, civic duty, and the roads leading toward Stormwind.",
    deep = "Its quest lines establish the kingdom's institutions and show how small disturbances connect to larger dangers across the Eastern Kingdoms.",
  },
  [1] = {
    arc = "Dun Morogh follows dwarven and gnomish communities facing troggs, rival clans, and the aftermath of Gnomeregan.",
    deep = "The region introduces Ironforge, gnomish displacement, and the cultural tensions that shape later Alliance stories.",
  },
  [3524] = {
    arc = "Azuremyst Isle begins the draenei story amid the wreckage of the Exodar and the consequences of its arrival on Azeroth.",
    deep = "The quests introduce draenei faith, technology, and responsibility while establishing their first relationships with the Alliance.",
  },
  [3483] = {
    arc = "Hellfire Peninsula opens Outland through a brutal campaign against the Burning Legion, fel orcs, and the shattered world's unstable frontier.",
    deep = "Alliance forces reconnect with old expedition survivors while the route establishes the military, demonic, and faction conflicts that span Outland.",
  },
  [3519] = {
    arc = "Terokkar Forest joins refugee stories, arakkoa mysteries, and the competing powers centered on Shattrath City.",
    deep = "Its arcs introduce the Lower City, Auchindoun, the Aldor and Scryers, and the histories that connect Draenor's peoples to Outland's present.",
  },
  [3520] = {
    arc = "Shadowmoon Valley confronts the strongest remaining forces of the Burning Legion and the legacy of the original Horde.",
    deep = "The zone's long chains tie together Illidan's rule, the fel orcs, the Netherwing, and the final preparation for Outland's major raids.",
  },
  [3522] = {
    arc = "Blade's Edge Mountains follows rival ogre clans, gronn, and factions trying to survive the harsh spine of Outland.",
    deep = "Its stories connect Rexxar, the Mok'Nathal, the Cenarion Expedition, Ogri'la, and the struggle over the region's ancient powers.",
  },
}

function MadsTBC:GetLore(zoneID, level)
  local zone = self.Zones and self.Zones[zoneID]
  local lore = self.Lore[zoneID]
  if level == "minimal" then return nil end
  if level == "route" then
    return "Route view: finish the available chains in " .. (zone and zone.name or "this zone") .. " before moving to the next coherent sweep."
  end
  if lore and level == "deep" then return lore.deep end
  if lore then return lore.arc end
  if level == "deep" then
    return "Deep lore notes for this zone will expand as its authored review is completed. Quest and prerequisite tracking is already active."
  end
  return "This arc follows the permanent and recurring stories associated with " .. (zone and zone.name or "the selected zone") .. "."
end
