"""Download the three NAB (Numenta Anomaly Benchmark) series the incidents use.

NAB is published by Numenta under a permissive licence:
https://github.com/numenta/NAB
"""

from pathlib import Path
from urllib.request import urlopen

BASE = "https://raw.githubusercontent.com/numenta/NAB/master/data/realAWSCloudwatch"

# local name -> NAB file
SERIES = {
    "ec2_cpu": "ec2_cpu_utilization_5f5533.csv",
    "rds_cpu": "rds_cpu_utilization_cc0c53.csv",
    "ec2_network_in": "ec2_network_in_257a54.csv",
}

out = Path(__file__).parent / "series"
out.mkdir(exist_ok=True)

for name, nab_file in SERIES.items():
    target = out / f"{name}.csv"
    if target.exists():
        print(f"ok    {target.name}")
        continue
    target.write_bytes(urlopen(f"{BASE}/{nab_file}").read())
    print(f"saved {target.name}")
