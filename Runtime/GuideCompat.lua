-- Compatibility bridge for the generated Guidelime-format guide modules.
-- The standalone runtime uses the generated manifest; these sources remain
-- available for Guidelime users and for authored-route review.
MadsTBC = MadsTBC or {}
MadsTBC.LegacyGuides = MadsTBC.LegacyGuides or {}

Guidelime = Guidelime or {}
if not Guidelime.registerGuide then
  function Guidelime.registerGuide(source, group)
    table.insert(MadsTBC.LegacyGuides, {source = source, group = group})
  end
end
