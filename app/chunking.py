from pathlib import Path

DOCS_DIR = Path("data/docs")

def split_document(path):
    lines = path.read_text(encoding="utf-8").splitlines()

    title = ""
    sections = []
    current_heading = None
    current_lines = []

    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            if current_heading is not None:
                sections.append((current_heading, current_lines))
            current_heading=line[3:].strip()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        sections.append((current_heading, current_lines))

    chunks = []
    for number, (heading, body_lines) in enumerate(sections, start=1):
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        chunks.append(
            {
                "id": f"{path.stem}-{number}",
                "text": f"{title} - {heading}\n{body}",
                "source": path.name,
                "section": heading,
            }
        )
    return chunks

def load_all_chunks(docs_dir=DOCS_DIR):
    chunks = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.extend(split_document(path))
    return chunks