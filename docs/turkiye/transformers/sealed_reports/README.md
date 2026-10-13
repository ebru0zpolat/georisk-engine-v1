# Mühürlü trafo raporları

`python scripts/transformer_audit.py` bu dizine `_{facility_id}_{YYYYMMDD}.md` üretir. Her dosyanın başında **YAML front matter** (makine okuması için) ve gövdede **repo HEAD mührü** bulunur.

Bu dosyaları versiyon kontrolüne alıp almama kurumsal politika ile belirlenir; repo dışı arşiv için ayrıca imzalı nesne (ör. release artefact) önerilir.
