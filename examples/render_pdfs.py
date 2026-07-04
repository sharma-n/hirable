#!/usr/bin/env python3
"""
Render all sample CV YAML files to PDF using RenderCV/Typst.
Run from the backend directory:
    cd backend && uv run python ../examples/render_pdfs.py
"""
import sys
from pathlib import Path

# Add backend app to path so we can import compile_pdf
backend_root = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_root))

from app.rendercv.compile import compile_pdf, CompileError

examples_dir = Path(__file__).parent

def main():
    """Compile all YAML files in examples/ to PDF."""
    yaml_files = sorted(examples_dir.glob("*.yaml"))
    if not yaml_files:
        print(f"No YAML files found in {examples_dir}")
        return 1

    success_count = 0
    failure_count = 0

    for yaml_path in yaml_files:
        pdf_path = yaml_path.with_suffix(".pdf")
        print(f"Rendering {yaml_path.name}...", end=" ", flush=True)

        try:
            source_text = yaml_path.read_text()
            pdf_bytes = compile_pdf(source_text)
            pdf_path.write_bytes(pdf_bytes)
            print(f"✓ ({len(pdf_bytes)} bytes)")
            success_count += 1
        except CompileError as e:
            print(f"✗ CompileError ({e.stage})")
            print(f"  {e}")
            failure_count += 1
        except Exception as e:
            print(f"✗ Error: {e}")
            failure_count += 1

    print(f"\nRendered {success_count} PDF(s), {failure_count} error(s).")
    return 0 if failure_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
