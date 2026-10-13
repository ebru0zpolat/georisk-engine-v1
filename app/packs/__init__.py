"""Country Pack namespace.

Country-specific regulation, report-template and disclosure logic lives here — never in
georisk-core (``app/scoring``, ``app/hazards``, ``app/loss``, ``app/adaptation`` …).
Adding a new country must require only a new ``app/packs/<iso2>/`` subtree, with zero core
changes (see ``GEORISK_ENGINE_REPOSITIONING.md`` §2).
"""
