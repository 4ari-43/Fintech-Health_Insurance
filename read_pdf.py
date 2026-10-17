
import pymupdf

def process_pdf(pdf_path):
    document = pymupdf.open(pdf_path)
    passages = []

    for page_index, page in enumerate(document):
        text = page.get_text("text")

        # Ignore pages with no extractable text
        if not text.strip():
            continue

        # Start with one passage per page
        passages.append({
            "text": text.strip(),
            "page": page_index + 1,
            "source": pdf_path
        })

    return passages


policy = process_pdf("policies/sample_cigna.pdf")

print("Passages extracted:", len(policy))
print("\nFirst passage:")
print(policy[0])
