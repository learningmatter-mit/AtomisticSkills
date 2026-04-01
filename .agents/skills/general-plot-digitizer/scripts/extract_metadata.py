"""
Extract plot metadata from an image using a Vision-Language Model API.

Calls Gemini or OpenAI API with the image and a JSON-schema-oriented prompt
(vlm_metadata_json_prompt.txt) to obtain axis labels, tick ranges, bounding
box, masks, and curve hints. Requires API key.

For narrative-only visual notes to a human/agent, use vlm_prompt_template.txt
(SKILL Phase 1); do not use that file with this script.

Usage:
    export GOOGLE_API_KEY=your_key
    python extract_metadata.py plot.png --output metadata.json

    # Optional: override Gemini model (default: lightweight gemini-2.5-flash-lite)
    python extract_metadata.py plot.png --gemini-model gemini-2.0-flash-lite

    export OPENAI_API_KEY=your_key
    python extract_metadata.py plot.png --provider openai --output metadata.json

Requirements:
    - Conda environment: base-agent
    - Optional: google-generativeai (for Gemini), openai (for OpenAI)
    - API key in environment
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Load .env from project root if present (enables GOOGLE_API_KEY without manual export)
try:
    from dotenv import load_dotenv
    for d in Path(__file__).resolve().parents:
        env_file = d / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break
except ImportError:
    pass

# Default: fast / cheap vision model (avoid heavier 2.x unless explicitly requested).
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"


def _script_dir() -> Path:
    return Path(__file__).resolve().parent


def load_json_metadata_prompt() -> str:
    """Load the VLM prompt used by this script (pipeline-shaped JSON only)."""
    template_path = _script_dir() / "vlm_metadata_json_prompt.txt"
    if not template_path.exists():
        skill_dir = _script_dir().parent
        template_path = skill_dir / "scripts" / "vlm_metadata_json_prompt.txt"
    with open(template_path, encoding="utf-8") as f:
        return f.read()


def load_narrative_prompt_template() -> str:
    """Load the narrative template for agent-in-the-loop use (not used by default here)."""
    template_path = _script_dir() / "vlm_prompt_template.txt"
    if not template_path.exists():
        skill_dir = _script_dir().parent
        template_path = skill_dir / "scripts" / "vlm_prompt_template.txt"
    with open(template_path, encoding="utf-8") as f:
        return f.read()


def metadata_schema_path() -> Path:
    return _script_dir().parent / "resources" / "metadata_schema.json"


def validate_metadata_schema(meta: dict, strict: bool) -> list[str]:
    """
    Validate metadata against resources/metadata_schema.json when jsonschema is installed.
    Returns a list of human-readable issue strings (empty if ok or skipped).
    """
    schema_file = metadata_schema_path()
    if not schema_file.is_file():
        return [f"Schema file not found: {schema_file}"]
    try:
        import jsonschema
    except ImportError:
        msg = "jsonschema not installed; pip install jsonschema to enable schema validation"
        if strict:
            return [msg]
        print(f"Warning: {msg}", file=sys.stderr)
        return []

    try:
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in schema file: {e}"]

    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(meta), key=lambda e: e.path)
    if not errors:
        return []
    lines = []
    for err in errors[:25]:
        loc = "/".join(str(p) for p in err.path) or "(root)"
        lines.append(f"{loc}: {err.message}")
    if len(errors) > 25:
        lines.append(f"... and {len(errors) - 25} more error(s)")
    if strict:
        for line in lines:
            print(f"Schema validation error: {line}", file=sys.stderr)
    else:
        print("Warning: metadata JSON does not fully match metadata_schema.json:", file=sys.stderr)
        for line in lines:
            print(f"  {line}", file=sys.stderr)
    return lines


def _normalize_comma_decimals(text: str) -> str:
    """Convert European comma decimals to dots before JSON parsing.
    E.g. 0,2 -> 0.2, 1,234 -> 1.234. Avoids touching strings inside quotes.
    """
    # Replace comma between digits (not inside strings) - simple pattern for numeric values
    return re.sub(r"(\d),(\d)", r"\1.\2", text)


def extract_json_from_response(text: str) -> dict:
    """Extract JSON object from VLM response (may be wrapped in markdown)."""
    text = text.strip()
    # Remove markdown code blocks if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
        text = _normalize_comma_decimals(text)
        return json.loads(text)
    return json.loads(_normalize_comma_decimals(text))


def call_gemini(
    image_path: str, prompt: str, model_name: str | None = None
) -> dict:
    """Call Gemini API with image and prompt. Returns parsed JSON."""
    try:
        from google import genai
    except ImportError:
        raise RuntimeError(
            "google-genai not installed. Run: pip install google-genai"
        )

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable not set")

    resolved = (
        model_name
        or os.environ.get("GEMINI_MODEL", "").strip()
        or DEFAULT_GEMINI_MODEL
    )

    import PIL.Image

    client = genai.Client(api_key=api_key)
    img = PIL.Image.open(image_path)
    response = client.models.generate_content(
        model=resolved, contents=[prompt, img]
    )
    text = response.text
    return extract_json_from_response(text)


def call_openai(image_path: str, prompt: str) -> dict:
    """Call OpenAI API (GPT-4o) with image and prompt. Returns parsed JSON."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai not installed. Run: pip install openai")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)

    import base64

    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = Path(image_path).suffix.lower()
    media_type = "image/png" if ext == ".png" else "image/jpeg"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{b64}"},
                    },
                ],
            }
        ],
        max_tokens=2048,
    )
    text = response.choices[0].message.content
    return extract_json_from_response(text)


def validate_metadata(meta: dict) -> dict:
    """Ensure metadata has required fields and correct types."""
    required = {
        "plot_title": "",
        "x_axis_label": "",
        "y_axis_label": "",
        "x_tick_min": 0.0,
        "x_tick_max": 1.0,
        "y_tick_min": 0.0,
        "y_tick_max": 1.0,
        "x_scale": "linear",
        "y_scale": "linear",
        "bounding_box": {"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 100},
    }
    for k, default in required.items():
        if k not in meta:
            meta[k] = default
    bb = meta["bounding_box"]
    if not isinstance(bb, dict):
        meta["bounding_box"] = required["bounding_box"]
    else:
        for k in ("x_min", "y_min", "x_max", "y_max"):
            if k not in bb:
                bb[k] = required["bounding_box"][k]
            else:
                bb[k] = int(bb[k])
    for k in ("x_tick_min", "x_tick_max", "y_tick_min", "y_tick_max"):
        meta[k] = float(meta[k])
    if meta["x_scale"] not in ("linear", "log"):
        meta["x_scale"] = "linear"
    if meta["y_scale"] not in ("linear", "log"):
        meta["y_scale"] = "linear"
    for k in ("x_reversed", "y_reversed"):
        if k not in meta:
            meta[k] = False
        else:
            meta[k] = bool(meta[k])
    if "y_calibration" in meta and meta["y_calibration"] not in ("axis", "per_curve_normalized"):
        meta["y_calibration"] = "axis"
    # Patch text_regions: ensure y_max is present (VLMs sometimes omit it)
    _default_text_h = 20
    for tr in meta.get("text_regions", []):
        if isinstance(tr, dict):
            for coord in ("x_min", "y_min", "x_max"):
                if coord in tr:
                    tr[coord] = int(tr[coord])
            if "y_max" not in tr and "y_min" in tr:
                tr["y_max"] = tr["y_min"] + _default_text_h
            elif "y_max" in tr:
                tr["y_max"] = int(tr["y_max"])
    # Patch curves[].region: ensure both y_min and y_max are ints
    for c in meta.get("curves", []):
        if isinstance(c, dict) and "region" in c:
            r = c["region"]
            for coord in ("y_min", "y_max"):
                if coord in r:
                    r[coord] = int(r[coord])
    # Optional sanity check: warn if bounding box seems unusual
    bb = meta["bounding_box"]
    w = bb.get("x_max", 0) - bb.get("x_min", 0)
    h = bb.get("y_max", 0) - bb.get("y_min", 0)
    if w < 50 or h < 50:
        print(
            f"Warning: bounding_box very small ({w}x{h} px). Verify it encloses the data region.",
            file=sys.stderr,
        )
    if w > 4000 or h > 4000:
        print(
            f"Warning: bounding_box very large ({w}x{h} px). Verify coordinates.",
            file=sys.stderr,
        )
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract plot metadata from image using VLM API"
    )
    parser.add_argument("image", help="Path to plot image")
    parser.add_argument(
        "--output",
        "-o",
        default="metadata.json",
        help="Output JSON path (default: metadata.json)",
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "openai"],
        default="gemini",
        help="VLM provider (default: gemini)",
    )
    parser.add_argument(
        "--gemini-model",
        default=None,
        metavar="MODEL",
        help=(
            f"Gemini model id for metadata extraction (default: {DEFAULT_GEMINI_MODEL} "
            "or GEMINI_MODEL env)"
        ),
    )
    parser.add_argument(
        "--narrative-prompt",
        action="store_true",
        help="Use vlm_prompt_template.txt instead of JSON prompt (not recommended; for debugging)",
    )
    parser.add_argument(
        "--strict-metadata-schema",
        action="store_true",
        help="Exit with error if metadata fails jsonschema validation against metadata_schema.json",
    )
    args = parser.parse_args()

    if not Path(args.image).exists():
        print(f"Error: Image not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    prompt = (
        load_narrative_prompt_template()
        if args.narrative_prompt
        else load_json_metadata_prompt()
    )

    try:
        if args.provider == "gemini":
            meta = call_gemini(args.image, prompt, model_name=args.gemini_model)
        else:
            meta = call_openai(args.image, prompt)
    except Exception as e:
        print(f"Error calling VLM: {e}", file=sys.stderr)
        sys.exit(1)

    meta = validate_metadata(meta)
    schema_issues = validate_metadata_schema(meta, strict=args.strict_metadata_schema)
    if args.strict_metadata_schema and schema_issues:
        sys.exit(1)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved metadata to {args.output}")


if __name__ == "__main__":
    main()
