"""Regenerate the checked-in JSON v2 examples and discriminated JSON Schema."""
import json
from pathlib import Path
from content_types import REGISTRY, sample_document


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    string = dict(type="string", minLength=1)
    strings = dict(type="array", minItems=1, items=string)
    seconds = dict(type="integer", minimum=0, maximum=30)
    def objects(properties, required):
        return dict(type="object", properties=properties, required=required)
    special = {
        "multiple_choice": dict(options=dict(type="array", minItems=4, maxItems=4, items=string), answer=dict(enum=list("ABCD"))),
        "error_correction": dict(highlight=objects(dict(wrong=string, correct=string, occurrence=dict(type="integer", minimum=1), start=dict(type="integer", minimum=0)), ["wrong", "correct"])),
        "fill_blank": dict(completed_sentence=string),
        "word_order": dict(tokens=dict(type="array", minItems=1, items=objects(dict(id=string, text=string), ["id", "text"])), answer_order=dict(**strings, uniqueItems=True)),
        "translation": dict(source_language=dict(enum=["vi", "en"]), target_language=dict(enum=["vi", "en"]), suggested_answers=strings, show_alternatives=dict(type="boolean")),
        "listening": dict(replay_count=dict(type="integer", minimum=1, maximum=5)),
        "dialogue": dict(dialogue=dict(type="array", minItems=2, items=objects(dict(speaker=string, text=string), ["speaker", "text"])), missing_turn_index=dict(type="integer", minimum=0), suggested_answers=strings),
        "true_false": dict(answer=dict(type="boolean"), correction=string),
        "multiple_meanings": dict(senses=dict(type="array", minItems=1, items=objects(dict(phrase=string, meaning=string, example=string), ["phrase", "meaning", "example"]))),
        "sentence_upgrade": dict(example_context=string),
        "phrase_lesson": dict(example_translation=string),
    }
    extra_required = dict(multiple_choice=["options", "answer"], error_correction=["highlight"], word_order=["tokens", "answer_order"], translation=["suggested_answers"], dialogue=["dialogue", "missing_turn_index", "suggested_answers"], true_false=["answer"], multiple_meanings=["senses"])
    definitions = {}
    for key, spec in REGISTRY.items():
        properties = dict(id=string, type=dict(const=key), subject=string, prompt=string, thinking_seconds=seconds, explanation=dict(type="string"))
        properties.update({field: string for field in spec.required})
        properties.update(special[key])
        definitions[key] = objects(properties, ["type", *spec.required, *extra_required.get(key, [])])
        write(Path("examples/v2") / f"{key}.json", sample_document(key))
    write(Path("examples/v2/mixed.json"), sample_document("mixed"))
    root = objects(dict(schema_version=dict(const=2), title=dict(type="string"), mode=dict(enum=[*REGISTRY, "mixed"]), settings=objects(dict(thinking_seconds=seconds), []), items=dict(type="array", minItems=1, items=dict(oneOf=[{"$ref": f"#/$defs/{key}"} for key in REGISTRY]))), ["schema_version", "items"])
    root.update({"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": definitions})
    root["allOf"] = [{"if": {"properties": {"mode": {"const": key}}, "required": ["mode"]}, "then": {"properties": {"items": {"items": {"$ref": f"#/$defs/{key}"}}}}} for key in REGISTRY]
    write(Path("docs/content-v2.schema.json"), root)


if __name__ == "__main__":
    main()
