
from pathlib import Path

import jsonschema
import yaml

from idl2icd.config import ProjectConfig
from idl2icd.model.metadata_schema import MetadataFile

EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "robot-fleet"


def test_generated_metadata_schema_validates_real_example_yaml():
    schema = MetadataFile.model_json_schema()
    data = yaml.safe_load((EXAMPLE_DIR / "metadata" / "telemetry.yaml").read_text())
    jsonschema.validate(data, schema)  # raises if invalid


def test_generated_metadata_schema_rejects_unknown_keys():
    schema = MetadataFile.model_json_schema()
    bad = {"topics": {"Foo": {"not_a_real_field": 123}}}
    import pytest
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_generated_config_schema_validates_real_example_config():
    schema = ProjectConfig.model_json_schema()
    data = yaml.safe_load((EXAMPLE_DIR / "idl2icd.yaml").read_text())
    jsonschema.validate(data, schema)
