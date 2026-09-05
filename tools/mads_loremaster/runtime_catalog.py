"""Character-neutral facts. Legacy authored coverage never controls this catalog."""
from collections import Counter
from dataclasses import replace
from pathlib import Path

from .catalog import quest_kinds, category_for, ZONE_NAME_OVERRIDES
from .model import Catalog, CatalogEntry
from .questie import load_quests, load_quest_sources, load_zones, load_sort_names, load_quest_tags, load_blacklist, resolve_questie_root

CLASSES = ('WARRIOR', 'PALADIN', 'HUNTER', 'ROGUE', 'PRIEST', 'SHAMAN', 'MAGE', 'WARLOCK', 'DRUID')


def runtime_records(legacy: Catalog):
    root = resolve_questie_root(legacy.source_path)
    zones = load_zones(root)
    zones.update(load_sort_names(root))
    zones.update(ZONE_NAME_OVERRIDES)
    base = load_quests(root, context=None)
    # Identical facts across character contexts share one variant.
    variants = {}
    source_inputs = dict(base)
    synthetic_id = max(base) + 1
    for faction, race in [('Alliance', 'Human'), ('Alliance', 'Other'), ('Horde', 'Other')]:
        for cls in CLASSES:
            context = (faction, cls, race)
            for qid, quest in load_quests(root, context=context).items():
                if qid not in base or quest.values != base[qid].values:
                    key = (qid, repr(quest.values))
                    if key not in variants:
                        variants[key] = [quest, [], synthetic_id]
                        source_inputs[synthetic_id] = quest
                        synthetic_id += 1
                    variants[key][1].append(':'.join(context))
    sources = load_quest_sources(root, source_inputs, zones)
    tags = load_quest_tags(root, int(legacy.phase_profile['phase']))
    # Evaluate every phase, including lower ones, instead of retaining only the
    # rows unavailable relative to today's packaged phase.
    phase_rules = {phase: load_blacklist(root, phase) for phase in range(1, 6)}
    catalog = Catalog(legacy.source_path, legacy.source_revision, scope=legacy.scope,
                      phase_profile=legacy.phase_profile, content_policy=legacy.content_policy, zones=zones)
    audit = []

    def enrich(q, key):
        return replace(q, starter_sources=sources[key][0], finisher_sources=sources[key][1],
                       objective_sources=sources[key][2], tag_id=tags.get(q.id, (None, None))[0],
                       tag_name=tags.get(q.id, (None, None))[1])

    def entry(q):
        historical = legacy.entries.get(q.id)
        return CatalogEntry(q, 'runtime', category=category_for(q),
                            order=historical.order if historical and historical.status.startswith('covered') else None,
                            conditional_categories=quest_kinds(q))

    from .runtime_manifest import _quest_record
    records = {}
    allowed_supplements = set(legacy.content_policy.get('covered_correction_only_allowlist', []))
    for qid, quest in sorted(base.items()):
        reason = None
        if quest.content_era != 'pre_cataclysm' and qid not in allowed_supplements:
            reason = 'unreviewed_correction_only'
        elif not quest.name or (quest.name.upper() == 'TEST' or quest.name.upper().startswith(('TEST -', 'TEST:', 'BETA ', '[PH]'))):
            reason = 'test_or_internal'
        elif int(quest.get('required_level', 0)) > 70:
            reason = 'above_max_level'
        decisions = [phase_rules[p].get(qid) for p in range(1, 6)]
        if all(d and d.reason_code in {'test_or_internal', 'duplicate', 'obsolete'} for d in decisions):
            reason = decisions[0].reason_code
        audit.append({'id': qid, 'status': 'excluded' if reason else 'included', 'reason': reason})
        if reason:
            continue
        q = enrich(quest, qid)
        record = _quest_record(entry(q), catalog)
        record['availabilityByPhase'] = [
            ('event' if d.reason_code in {'event_inactive', 'event'} else
             'future' if d.reason_code == 'future_phase' else 'unavailable') if d else 'current'
            for d in decisions
        ]
        record['unknownAvailability'] = not bool(q.get('started_by'))
        records[qid] = record
    for (qid, _), (quest, contexts, key) in variants.items():
        if qid not in records:
            continue
        derived = _quest_record(entry(enrich(quest, key)), catalog)
        derived["unknownAvailability"] = not bool(quest.get("started_by"))
        original = records[qid]
        patch = {k: v for k, v in derived.items() if original.get(k) != v and v is not None}
        clear = [k for k, v in derived.items() if v is None and original.get(k) is not None]
        if patch or clear:
            original.setdefault('variants', []).append({'contexts': contexts, 'fields': patch, 'clear': clear})
    # Dependency/choice components are generated once. Runtime verifies viability
    # with the current character, rather than selecting the lowest quest ID.
    links = {qid: set() for qid in records}
    for qid, record in records.items():
        for other in record.get('exclusiveTo', []):
            if other in links:
                links[qid].add(other)
                links[other].add(qid)
    components, visited = [], set()
    for qid in sorted(links):
        if not links[qid] or qid in visited:
            continue
        todo, component = [qid], []
        while todo:
            node = todo.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            todo.extend(links[node] - visited)
        components.append(sorted(component))
    return records, catalog, {'sourceRevision': legacy.source_revision, 'sourceRows': len(base), 'records': audit,
                              'counts': dict(Counter(r['status'] for r in audit)), 'choiceComponents': components}
