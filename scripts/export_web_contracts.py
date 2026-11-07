"""Export the Python-owned JSON schema; pipe into the web generator or compare in CI."""

import json

from skye.web_contracts import WebContract

if __name__ == "__main__":
    print(json.dumps(WebContract.model_json_schema(), indent=2, sort_keys=True))
