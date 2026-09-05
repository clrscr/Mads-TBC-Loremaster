-- Legacy chapters have their original Night Elf Hunter audience. Their presence
-- does not define standalone quest coverage or impersonate another addon.
MadsTBC.LegacyGuides = {}
function MadsTBC.RegisterLegacyGuide(source, group)
  if Guidelime and type(Guidelime.registerGuide) == "function" then
    Guidelime.registerGuide(source, group)
  else
    table.insert(MadsTBC.LegacyGuides, {source=source, group=group})
  end
end
