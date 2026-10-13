.PHONY: verify verify-eal

# Human-readable walkthrough for one asset (writes verification_report.md).
# Usage: make verify ASSET=vf-001-hotel-coast
verify:
	@test -n "$(ASSET)" || (echo "Usage: make verify ASSET=<asset_id>"; exit 2)
	PYTHONPATH=. python scripts/verify_eal.py --asset "$(ASSET)" --report verification_report.md

# CI-style sample of N=5 assets seeded by git commit SHA.
verify-eal:
	PYTHONPATH=. python scripts/verify_eal.py --sample 5 --seed-from-git --report verification_report.md
