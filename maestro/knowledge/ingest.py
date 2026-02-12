# ingest.py - Build knowledge_store from construction plan PDFs

from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image

from gemini_service import _save_trace, run_pass1, run_pass2


MAX_GEMINI_BYTES = 9 * 1024 * 1024  # 9 MB (Gemini limit is 10 MB, leave margin)


def _resize_for_gemini(page_png: Path) -> Path:
    """If page_png exceeds MAX_GEMINI_BYTES, return a resized copy. Otherwise return original."""
    if page_png.stat().st_size <= MAX_GEMINI_BYTES:
        return page_png

    resized_path = page_png.with_name("page_pass1.png")
    img = Image.open(page_png)
    w, h = img.size

    # Shrink by 50% — typically cuts filesize to ~1/3
    new_w, new_h = w // 2, h // 2
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    resized.save(resized_path, "PNG")

    # If still too big, shrink again
    if resized_path.stat().st_size > MAX_GEMINI_BYTES:
        img2 = Image.open(resized_path)
        w2, h2 = img2.size
        resized2 = img2.resize((w2 // 2, h2 // 2), Image.LANCZOS)
        resized2.save(resized_path, "PNG")

    return resized_path


def render_page(pdf_path: str | Path, page_num: int, output_path: str | Path, dpi: int = 200) -> tuple[int, int]:
    """Render a PDF page to PNG. Returns (width, height)."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with fitz.open(str(pdf_path)) as doc:
        page = doc[page_num]
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pix.save(str(output))
        return pix.width, pix.height


def _infer_discipline(path: Path) -> str:
    haystack = f"{path.as_posix()} {path.stem}".lower()

    if (
        "architectural" in haystack
        or "arch" in haystack
        or re.search(r"(^|[^a-z])a\d{2,4}([^a-z]|$)", haystack)
        or "a-" in haystack
    ):
        return "Architectural"

    if (
        "mep" in haystack
        or "mechanical" in haystack
        or "electrical" in haystack
        or "plumbing" in haystack
        or "fire protection" in haystack
        or "hvac" in haystack
        or re.search(r"(^|[^a-z])(m|e|p|fp)\d{2,4}([^a-z]|$)", haystack)
        or "m-" in haystack
        or "e-" in haystack
        or "p-" in haystack
        or "fp-" in haystack
    ):
        return "MEP"

    if (
        "structural" in haystack
        or "struct" in haystack
        or re.search(r"(^|[^a-z])s\d{2,4}([^a-z]|$)", haystack)
        or "s-" in haystack
    ):
        return "Structural"

    return "General"


def discover_pdfs(folder: str | Path) -> list[dict[str, Any]]:
    """Scan folder recursively for PDFs."""
    root = Path(folder).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Folder not found: {root}")

    pdf_paths = sorted(root.rglob("*.pdf"), key=lambda p: p.as_posix().lower())
    discovered: list[dict[str, Any]] = []

    for pdf_path in pdf_paths:
        try:
            with fitz.open(str(pdf_path)) as doc:
                page_count = int(doc.page_count)
        except Exception as exc:
            print(f"[WARN] Skipping unreadable PDF '{pdf_path}': {exc}")
            continue

        if page_count <= 0:
            print(f"[WARN] Skipping empty PDF '{pdf_path}'")
            continue

        discovered.append(
            {
                "path": str(pdf_path),
                "name": pdf_path.name,
                "page_count": page_count,
                "discipline": _infer_discipline(pdf_path),
            }
        )

    return discovered


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def generate_region_id(bbox: dict[str, Any]) -> str:
    """Deterministic ID from bbox position: r_x0_y0_x1_y1."""
    x0 = _to_int(bbox.get("x0"), 0)
    y0 = _to_int(bbox.get("y0"), 0)
    x1 = _to_int(bbox.get("x1"), 0)
    y1 = _to_int(bbox.get("y1"), 0)
    return f"r_{x0}_{y0}_{x1}_{y1}"


def crop_region_pil(image_path: str | Path, bbox: dict[str, Any], output_path: str | Path, padding: int = 20) -> None:
    """Fallback: PIL crop using 0-1000 normalized bbox."""
    from PIL import Image

    img = Image.open(image_path)
    w, h = img.size

    x0 = max(0, int((_to_int(bbox.get("x0"), 0) / 1000.0) * w) - padding)
    y0 = max(0, int((_to_int(bbox.get("y0"), 0) / 1000.0) * h) - padding)
    x1 = min(w, int((_to_int(bbox.get("x1"), 1000) / 1000.0) * w) + padding)
    y1 = min(h, int((_to_int(bbox.get("y1"), 1000) / 1000.0) * h) + padding)

    if x1 <= x0:
        x1 = min(w, x0 + 1)
    if y1 <= y0:
        y1 = min(h, y0 + 1)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    img.crop((x0, y0, x1, y1)).save(str(output))


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _flatten_strings(value: Any) -> list[str]:
    items: list[str] = []
    if value is None:
        return items

    if isinstance(value, str):
        text = value.strip()
        if text:
            items.append(text)
        return items

    if isinstance(value, (int, float, bool)):
        items.append(str(value))
        return items

    if isinstance(value, list):
        for item in value:
            items.extend(_flatten_strings(item))
        return items

    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str):
                key_text = key.strip()
                if key_text:
                    items.append(key_text)
            items.extend(_flatten_strings(nested))
        return items

    return items


def _add_index_term(bucket: dict[str, list[dict[str, str]]], term: str, source: dict[str, str]) -> None:
    normalized = term.strip()
    if not normalized:
        return
    bucket.setdefault(normalized, [])
    if source not in bucket[normalized]:
        bucket[normalized].append(source)


_SHEET_PATTERN = re.compile(r"\b[A-Z]{1,3}-?\d{2,4}(?:\.\d+)?\b")


def _extract_cross_ref_targets(value: Any) -> list[str]:
    refs: list[str] = []

    if value is None:
        return refs

    if isinstance(value, str):
        matches = _SHEET_PATTERN.findall(value.upper())
        if matches:
            refs.extend(matches)
        else:
            text = value.strip()
            if text:
                refs.append(text)
        return refs

    if isinstance(value, list):
        for item in value:
            refs.extend(_extract_cross_ref_targets(item))
        return refs

    if isinstance(value, dict):
        preferred_keys = ("sheet", "sheet_number", "target", "page", "ref", "to")
        for key in preferred_keys:
            if key in value:
                refs.extend(_extract_cross_ref_targets(value.get(key)))
        if not refs:
            for nested in value.values():
                refs.extend(_extract_cross_ref_targets(nested))
        return refs

    return refs


def _normalize_modification(mod: Any) -> dict[str, str]:
    if isinstance(mod, dict):
        action = str(mod.get("action", mod.get("type", ""))).strip()
        item = str(mod.get("item", mod.get("what", mod.get("description", "")))).strip()
        note = str(mod.get("note", mod.get("details", ""))).strip()
        return {"action": action, "item": item, "note": note}

    if isinstance(mod, str):
        text = mod.strip()
        if not text:
            return {"action": "", "item": "", "note": ""}
        first = text.split(" ", 1)[0].lower()
        if first in {"install", "demo", "demolish", "protect", "remove", "replace"}:
            item = text[len(first) :].strip()
            return {"action": first, "item": item, "note": ""}
        return {"action": "", "item": text, "note": ""}

    return {"action": "", "item": "", "note": ""}


def build_index(project_dir: str | Path) -> dict[str, Any]:
    """Aggregate all pass1/pass2 data into index.json."""
    root = Path(project_dir)
    pages_dir = root / "pages"

    index_data: dict[str, Any] = {
        "materials": {},
        "keywords": {},
        "modifications": [],
        "cross_refs": {},
        "broken_refs": [],
        "pages": {},
        "summary": {
            "page_count": 0,
            "pointer_count": 0,
            "unique_material_count": 0,
            "unique_keyword_count": 0,
            "modification_count": 0,
            "broken_ref_count": 0,
        },
    }

    if not pages_dir.exists():
        out_path = root / "index.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2)
        return index_data

    page_dirs = [d for d in sorted(pages_dir.iterdir(), key=lambda p: p.name.lower()) if d.is_dir()]
    page_names = {d.name for d in page_dirs}

    for page_dir in page_dirs:
        page_name = page_dir.name
        pass1 = _load_json(page_dir / "pass1.json", {})
        if not isinstance(pass1, dict):
            pass1 = {}

        page_index = pass1.get("index", {})
        if not isinstance(page_index, dict):
            page_index = {}

        regions = pass1.get("regions", [])
        if not isinstance(regions, list):
            regions = []

        page_info = {
            "discipline": pass1.get("discipline", "General"),
            "page_type": pass1.get("page_type", "unknown"),
            "region_count": len(regions),
            "pointer_count": 0,
        }
        index_data["pages"][page_name] = page_info

        # Page-level terms
        for material in _flatten_strings(page_index.get("materials", [])):
            _add_index_term(index_data["materials"], material, {"page": page_name})

        for keyword in _flatten_strings(page_index.get("keywords", [])):
            _add_index_term(index_data["keywords"], keyword, {"page": page_name})

        # Page-level cross references
        for ref in _extract_cross_ref_targets(pass1.get("cross_references", [])):
            index_data["cross_refs"].setdefault(ref, [])
            if page_name not in index_data["cross_refs"][ref]:
                index_data["cross_refs"][ref].append(page_name)

        # Pointer-level data
        pointers_dir = page_dir / "pointers"
        pointer_dirs = [d for d in sorted(pointers_dir.iterdir(), key=lambda p: p.name.lower()) if d.is_dir()] if pointers_dir.exists() else []
        page_info["pointer_count"] = len(pointer_dirs)

        for pointer_dir in pointer_dirs:
            region_id = pointer_dir.name
            pass2 = _load_json(pointer_dir / "pass2.json", {})
            if not isinstance(pass2, dict):
                pass2 = {}

            source = {"page": page_name, "region_id": region_id}

            for material in _flatten_strings(pass2.get("materials", [])):
                _add_index_term(index_data["materials"], material, source)

            keyword_fields = [
                pass2.get("keynotes_referenced", []),
                pass2.get("keynotes", []),
                pass2.get("specifications", []),
            ]
            for field in keyword_fields:
                for keyword in _flatten_strings(field):
                    _add_index_term(index_data["keywords"], keyword, source)

            for mod_raw in pass2.get("modifications", []) if isinstance(pass2.get("modifications", []), list) else []:
                normalized = _normalize_modification(mod_raw)
                if not normalized["action"] and not normalized["item"] and not normalized["note"]:
                    continue
                mod_entry = {
                    "action": normalized["action"],
                    "item": normalized["item"],
                    "note": normalized["note"],
                    "source": source,
                }
                if mod_entry not in index_data["modifications"]:
                    index_data["modifications"].append(mod_entry)

            for ref in _extract_cross_ref_targets(pass2.get("cross_references", [])):
                index_data["cross_refs"].setdefault(ref, [])
                if page_name not in index_data["cross_refs"][ref]:
                    index_data["cross_refs"][ref].append(page_name)

    # Normalize cross-ref source lists and detect broken refs.
    normalized_cross_refs: dict[str, list[str]] = {}
    for target, refs_from in index_data["cross_refs"].items():
        deduped = sorted(set(refs_from))
        normalized_cross_refs[target] = deduped
    index_data["cross_refs"] = normalized_cross_refs

    broken_refs = sorted([target for target in index_data["cross_refs"] if target not in page_names])
    index_data["broken_refs"] = broken_refs

    # Summary counts
    index_data["summary"]["page_count"] = len(page_names)
    index_data["summary"]["pointer_count"] = sum(p["pointer_count"] for p in index_data["pages"].values())
    index_data["summary"]["unique_material_count"] = len(index_data["materials"])
    index_data["summary"]["unique_keyword_count"] = len(index_data["keywords"])
    index_data["summary"]["modification_count"] = len(index_data["modifications"])
    index_data["summary"]["broken_ref_count"] = len(index_data["broken_refs"])

    out_path = root / "index.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)

    return index_data


def get_page_name(pdf_path: str | Path, page_num: int) -> str:
    """Deterministic page name from source PDF and 1-based page number."""
    stem = Path(pdf_path).stem
    safe_stem = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_")
    if not safe_stem:
        safe_stem = "page"
    return f"{safe_stem}_p{page_num + 1:03d}"


def ingest(folder_path: str | Path) -> Path:
    folder = Path(folder_path).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Input folder not found: {folder}")

    project_name = folder.name
    store = Path("knowledge_store") / project_name
    store.mkdir(parents=True, exist_ok=True)

    pdfs = discover_pdfs(folder)
    if not pdfs:
        print(f"No PDFs found in {folder}")
        return store

    total_pages = sum(p["page_count"] for p in pdfs)
    page_counter = 0
    seen_page_names: set[str] = set()

    for pdf in pdfs:
        for pg in range(pdf["page_count"]):
            page_counter += 1

            base_page_name = get_page_name(pdf["path"], pg)
            page_name = base_page_name
            suffix = 2
            while page_name in seen_page_names:
                page_name = f"{base_page_name}_dup{suffix}"
                suffix += 1
            seen_page_names.add(page_name)

            page_dir = store / "pages" / page_name

            # Resume logic: skip pages that already have pass1.json + at least one pointer
            pass1_exists = (page_dir / "pass1.json").exists()
            pointers_dir_check = page_dir / "pointers"
            has_pointers = pointers_dir_check.exists() and any(pointers_dir_check.iterdir()) if pointers_dir_check.exists() else False
            if pass1_exists and has_pointers:
                print(f"[{page_counter}/{total_pages}] Skipping {page_name} (already complete)")
                continue

            # If partially complete (pass1 but no pointers), re-do from scratch
            if page_dir.exists():
                shutil.rmtree(page_dir)
            page_dir.mkdir(parents=True, exist_ok=True)

            print(f"[{page_counter}/{total_pages}] Rendering {page_name}...", end=" ", flush=True)
            width, height = render_page(pdf["path"], pg, page_dir / "page.png")
            print(f"done ({width}x{height})")

            # Resize for Gemini if over 9 MB (keeps full-res page.png for Pass 2 crops)
            pass1_image = _resize_for_gemini(page_dir / "page.png")
            if pass1_image != page_dir / "page.png":
                sz_mb = pass1_image.stat().st_size / 1024 / 1024
                print(f"  [Resized for Pass 1: {width}x{height} -> {width//2}x{height//2} ({sz_mb:.1f} MB)]")

            print(f"[{page_counter}/{total_pages}] Pass 1 {page_name}...", end=" ", flush=True)
            start = time.time()
            try:
                pass1 = run_pass1(pass1_image, page_name, pdf["discipline"])
            except Exception as exc:
                print(f"\n  [ERROR] Pass 1 failed: {exc}")
                pass1 = {
                    "page_name": page_name,
                    "page_type": "unknown",
                    "discipline": pdf["discipline"],
                    "regions": [],
                    "sheet_reflection": "",
                    "index": {},
                    "cross_references": [],
                    "sheet_info": {},
                    "processing_time_ms": 0,
                    "_crop_candidates": [],
                    "_trace": [{"type": "error", "content": str(exc)}],
                }
            elapsed = time.time() - start

            regions = pass1.get("regions", [])
            if not isinstance(regions, list):
                regions = []
                pass1["regions"] = regions

            for idx, region in enumerate(regions):
                if not isinstance(region, dict):
                    regions[idx] = {"bbox": {"x0": 0, "y0": 0, "x1": 1000, "y1": 1000}, "type": "unknown", "label": ""}
                    region = regions[idx]
                bbox = region.get("bbox", {})
                if not isinstance(bbox, dict):
                    bbox = {"x0": 0, "y0": 0, "x1": 1000, "y1": 1000}
                    region["bbox"] = bbox
                region["id"] = generate_region_id(bbox)

            crop_candidates = pass1.pop("_crop_candidates", [])
            if not isinstance(crop_candidates, list):
                crop_candidates = []

            _save_trace(pass1.get("_trace", []), crop_candidates, page_dir, prefix="pass1_img")

            with (page_dir / "pass1.json").open("w", encoding="utf-8") as f:
                json.dump(pass1, f, indent=2)

            print(f"{len(regions)} regions, {len(crop_candidates)} images ({elapsed:.1f}s)")

            for idx, region in enumerate(regions):
                region_id = region.get("id", f"region_{idx:03d}")
                pointer_dir = page_dir / "pointers" / region_id
                pointer_dir.mkdir(parents=True, exist_ok=True)

                bbox = region.get("bbox", {"x0": 0, "y0": 0, "x1": 1000, "y1": 1000})
                crop_region_pil(page_dir / "page.png", bbox, pointer_dir / "crop.png")

                label = region.get("label", region_id)
                print(f"  Pass 2 [{idx + 1}/{len(regions)}] {label}...", end=" ", flush=True)
                start = time.time()
                try:
                    pass2 = run_pass2(
                        crop_path=pointer_dir / "crop.png",
                        page_path=page_dir / "page.png",
                        region=region,
                        pass1_context=pass1,
                    )
                except Exception as exc:
                    pass2 = {
                        "content_markdown": "",
                        "materials": [],
                        "dimensions": [],
                        "keynotes_referenced": [],
                        "specifications": [],
                        "cross_references": [],
                        "coordination_notes": [],
                        "questions_answered": [],
                        "assembly": [],
                        "connections": [],
                        "areas": [],
                        "equipment": [],
                        "modifications": [],
                        "keynotes": [],
                        "schedule_type": "",
                        "columns": [],
                        "rows": [],
                        "note_categories": [],
                        "processing_time_ms": 0,
                        "_trace": [{"type": "error", "content": str(exc)}],
                        "_trace_images": [],
                    }
                elapsed = time.time() - start

                pass2_images = pass2.pop("_trace_images", [])
                if not isinstance(pass2_images, list):
                    pass2_images = []
                _save_trace(pass2.get("_trace", []), pass2_images, pointer_dir, prefix="trace_p2")

                with (pointer_dir / "pass2.json").open("w", encoding="utf-8") as f:
                    json.dump(pass2, f, indent=2)

                print(f"done ({elapsed:.1f}s)")

    print("Building index...", end=" ", flush=True)
    index_data = build_index(store)
    print("done")

    project_meta = {
        "name": project_name,
        "source_path": str(folder),
        "total_pages": total_pages,
        "disciplines": sorted(set(p["discipline"] for p in pdfs)),
        "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "index_summary": index_data.get("summary", {}),
    }
    with (store / "project.json").open("w", encoding="utf-8") as f:
        json.dump(project_meta, f, indent=2)

    print(f"\nIngestion complete: {total_pages} pages -> {store}")
    return store


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Usage: python ingest.py "<plans_folder>"')
        raise SystemExit(1)
    ingest(sys.argv[1])

