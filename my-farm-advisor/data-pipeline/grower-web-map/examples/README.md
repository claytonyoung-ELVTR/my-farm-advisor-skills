# Examples

This folder documents usage examples for the grower web map. Generated HTML maps are runtime outputs and are not committed.

## Generate every grower

```bash
export DATA_PIPELINE_DATA_ROOT=/absolute/path/to/my-farm-advisor-runtime
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src"
"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  scripts/reporting/generate_grower_web_map.py --all
```

Expected outputs:

```text
${DATA_PIPELINE_DATA_ROOT}/data-pipeline/growers/il-grower/derived/reports/il-grower_web_map.html
${DATA_PIPELINE_DATA_ROOT}/data-pipeline/growers/ia-grower/derived/reports/ia-grower_web_map.html
```

## Generate one grower to a temporary path

```bash
cd "${DATA_PIPELINE_DATA_ROOT}/data-pipeline/src"
"${DATA_PIPELINE_DATA_ROOT}/data-pipeline/.venv/bin/python" \
  scripts/reporting/generate_grower_web_map.py \
  --grower-slug ia-grower \
  --output /tmp/ia-grower_web_map.html
```

Open the HTML file in a browser. The map needs internet access for the MapLibre library and the satellite tiles.

## Inspect the embedded payload

```bash
python3 - <<'PY'
import json
import re
from pathlib import Path

path = Path("/tmp/ia-grower_web_map.html")
text = path.read_text()
match = re.search(
    r'<script id="grower-data" type="application/json">(.*?)</script>',
    text,
    re.S,
)
data = json.loads(match.group(1))
print(data["grower"])
print(data["stats"])
for feature in data["fields"]["features"]:
    props = feature["properties"]
    print(props["field_name"], props["farm_name"], props["area_acres"])
PY
```

See [../GUIDE.md](../GUIDE.md) for the full behavior and troubleshooting reference.
